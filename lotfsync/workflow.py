"""Input discovery and atomic output package creation; never overwrite sources."""
from pathlib import Path, PurePosixPath
from dataclasses import dataclass
from datetime import datetime, timezone
import json, re, shutil, uuid, zipfile
from .engine import read_save, synchronize, Options, sha, children, root_properties, contents, raw
from .errors import SyncError, FormatError

MAX_SAVE = 64*1024*1024
SLOT = re.compile(r'^Save\d+\.sav$', re.I)

@dataclass(frozen=True)
class Source:
    path: Path
    kind: str
    slots: tuple

    @classmethod
    def discover(cls, path):
        p=Path(path).expanduser().resolve()
        if p.is_dir():
            slots=tuple(sorted(x.name for x in p.iterdir() if x.is_file() and SLOT.fullmatch(x.name)))
            kind='folder'
        elif p.suffix.lower()=='.zip':
            if p.stat().st_size>256*1024*1024:
                raise SyncError('input_too_large')
            with zipfile.ZipFile(p) as z:
                if len(z.infolist())>10000:
                    raise SyncError('input_too_large')
                names=z.namelist()
                if len(names)!=len(set(names)):
                    raise SyncError('duplicate_zip')
                slots=tuple(sorted(n for n in names if SLOT.fullmatch(PurePosixPath(n).name) and not n.startswith('__MACOSX/')))
            kind='zip'
        elif p.is_file() and SLOT.fullmatch(p.name):
            # A selected .sav still discovers only its own rotating backups.
            slots=(p.name,);kind='file'
        else:
            raise SyncError('character_required')
        if not slots:
            raise SyncError('no_slots')
        return cls(p,kind,slots)

    def read(self, key):
        if self.kind=='zip':
            with zipfile.ZipFile(self.path) as z:
                info=z.getinfo(key)
                if info.file_size>MAX_SAVE or info.flag_bits&1:
                    raise SyncError('input_too_large')
                with z.open(info) as f:
                    data=f.read(MAX_SAVE+1)
        else:
            base=self.path if self.kind=='folder' else self.path.parent
            target=base/key
            if target.stat().st_size>MAX_SAVE:
                raise SyncError('input_too_large')
            data=target.read_bytes()
        if len(data)>MAX_SAVE:
            raise SyncError('input_too_large')
        return data

    def keys(self, slot, include_backups):
        if slot not in self.slots:
            raise SyncError('select_slot')
        if not include_backups:
            return [slot]
        if self.kind=='zip':
            with zipfile.ZipFile(self.path) as z:
                available=z.namelist()
        else:
            base=self.path if self.kind=='folder' else self.path.parent
            available=[x.name for x in base.iterdir() if x.is_file()]
        result=[slot]
        for suffix in ('_b1','_b2'):
            expected=slot[:-4]+suffix+slot[-4:]
            matches=[n for n in available if n.casefold()==expected.casefold()]
            if len(matches)>1:
                raise SyncError('duplicate_zip')
            result.extend(matches)
        return result

@dataclass
class ReadSnapshot:
    source: Source
    key: str
    data: bytes

    def unchanged(self):
        if self.source.read(self.key)!=self.data:
            raise SyncError('input_changed', self.key)

@dataclass
class Prepared:
    host: object
    guest: object
    snapshots: list
    outputs: list
    reports: list
    options: Options


def character_identity(save):
    # ObjectRecordDetails.ID changes between rotating saves; it is not a player ID.
    # The format has no demonstrated stable character GUID. Compare name/class,
    # then rely on the explicitly selected slot and its matching backup filenames.
    b=save.payload;r=root_properties(b)
    return (save.info['player'], raw(b,r['CharacterClassName']), raw(b,r['CharacterClassStatsRowHandle']))


def prepare(host_source, host_slot, guest_source, guest_slot, options, include_backups=True, progress=lambda text:None):
    progress('reading_host')
    hb=host_source.read(host_slot);host=read_save(hb)
    snapshots=[ReadSnapshot(host_source,host_slot,hb)]
    outputs,reports=[],[];main=None
    for key in guest_source.keys(guest_slot,include_backups):
        progress('checking:'+PurePosixPath(key).name)
        data=guest_source.read(key)
        guest=read_save(data)
        if main is None:
            main=guest
        elif character_identity(guest)!=character_identity(main):
            raise SyncError('backup_identity',key)
        if host_source.path==guest_source.path and key==host_slot:
            raise SyncError('same_input')
        result,report=synchronize(guest,host,options)
        name=PurePosixPath(key).name
        report['file']=name
        report['guest_before']=guest.info
        report['guest_after']=read_save(result).info
        snapshots.append(ReadSnapshot(guest_source,key,data))
        outputs.append((name,result));reports.append(report)
    # Analyze returns only when every selected file has passed verification.
    return Prepared(host,main,snapshots,outputs,reports,options)


def create_output(prepared, destination, docs_dir):
    for snap in prepared.snapshots:
        snap.unchanged()
    dest=Path(destination).expanduser().resolve()
    if not dest.is_dir():
        raise SyncError('output_folder')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    token=uuid.uuid4().hex[:8]
    name=f'LOTF_Sync_{stamp}_{token}'
    staging=dest/('.'+name+'.partial')
    final=dest/name
    staging.mkdir(exist_ok=False)
    try:
        (staging/'CORRECTED').mkdir();(staging/'BACKUP_GUEST').mkdir()
        for name,data in prepared.outputs:
            p=staging/'CORRECTED'/name;p.write_bytes(data)
            if p.read_bytes()!=data:
                raise OSError('Output read-back mismatch')
        for snap in prepared.snapshots[1:]:
            p=staging/'BACKUP_GUEST'/PurePosixPath(snap.key).name;p.write_bytes(snap.data)
            if p.read_bytes()!=snap.data:
                raise OSError('Backup read-back mismatch')
        report=dict(application='LOTF Save Sync',version='1.0.1',created_utc=datetime.now(timezone.utc).isoformat(),
                    host=prepared.host.info,options=prepared.options.keys(),source_files_unchanged=True,
                    files=prepared.reports,in_game_tested_by_this_program=False)
        (staging/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        for lang in ('IT','EN'):
            shutil.copyfile(Path(docs_dir)/f'GUIDE_{lang}.txt',staging/f'GUIDE_{lang}.txt')
        # Guard against a game/cloud write that happened while preparing the output.
        for snap in prepared.snapshots:
            snap.unchanged()
        staging.rename(final)
    except Exception:
        shutil.rmtree(staging,ignore_errors=True)
        raise
    return final
