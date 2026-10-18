"""Selective, offline LOTF2 save synchronization. No in-place writes.

The full selection reproduces the V4 repair tested in game on build 2.5.624.
Unknown versions and uncertain checkpoint layouts are rejected.
"""
from dataclasses import dataclass
import json
from .schema import *
from .records import parse_records
from .dynamic import dynamic_records, dynamic_registry
from .references import all_records, check_record, NATIVE_TAILS
from .errors import SyncError

SUPPORTED_VERSION = '2.5.624'
MOD_ENABLED = 'GameState.HexGameplayModifiersEnabled'
PASSAGES = CLASS_PREFIXES[:2]
STORY_CLASSES = CLASS_PREFIXES[2:-1]
ANCHORS = CLASS_PREFIXES[-1:]
MANUAL_CLASSES = ('/Game/Blueprints/Data/Character/NPCs/', '/Game/Blueprints/Data/Character/Enemies/Bosses/')
PROTECTED = ('PlayerInventoryData', 'PlayerStatsData', 'CustomizationSettingsData', 'PlayerName',
             'PlayerStance', 'CharacterClassStatsRowHandle', 'NewGameManagerData', 'VendorVisitedItems',
             'bSaveGameInvalid', 'InvalidSaveGameReason', 'DifficultyMode')

@dataclass(frozen=True)
class Options:
    modifiers: bool = True
    story: bool = True
    passages: bool = True
    checkpoints: bool = True

    def keys(self):
        return [k for k in self.__dataclass_fields__ if getattr(self, k)]

@dataclass
class Save:
    data: bytes
    header: bytes
    chunks: list
    payload: bytes
    info: dict


def require(condition, text):
    if not condition:
        raise FormatError(text)


def read_save(data):
    header, chunks, b = strict_read(data)
    if not header.endswith(b'/Script/LOTF2.LOTF2SaveGame\0'):
        raise SyncError('character_required')
    r, w, q, g = locate(b)
    version = '.'.join(str(r[k]['value']) for k in ('GameVersionMajor', 'GameVersionMilestone', 'GameVersionMinor'))
    ng = object_data(b, r, 'NewGameManagerData')[3]['newGameLevel']['value']
    # Legacy is serialized as the missing/default difficulty in the tested build.
    difficulty = r.get('DifficultyMode', {}).get('value', 'Legacy (default)')
    world = json.loads(w['value'])
    require(isinstance(world, dict), 'World state is not a JSON object')
    tags = [k for k, _ in tag_entries(b, g)]
    info = dict(player=r['PlayerName']['value'], version=version, master_version=r['MasterSaveVersion']['value'],
                ng=ng, difficulty=difficulty, checkpoint=r['BoundAnchorName']['value'],
                map=r['LevelName']['value'], date=r.get('Date', {}).get('value', ''),
                modifiers={k:v for k,v in world.items() if k.startswith(PREFIX)},
                modifier_tags=[k for k in tags if k.startswith(PREFIX) or k == MOD_ENABLED],
                anchors=anchor_map(b), sha256=sha(data), bytes=len(data),
                saved_diagnostic=r.get('InvalidSaveGameReason', {}).get('value', ''))
    require(rebuild(header, chunks, b)[0] == data, 'Lossless container round-trip failed')
    return Save(data, header, chunks, b, info)


def check_pair(guest, host, opt):
    if not opt.keys():
        raise SyncError('select_option')
    if any(s.info['version'] != SUPPORTED_VERSION or s.info['master_version'] != 12 for s in (guest, host)):
        raise SyncError('unsupported_version', SUPPORTED_VERSION)
    if guest.info['ng'] != host.info['ng']:
        raise SyncError('ng_mismatch')
    if guest.info['difficulty'] != host.info['difficulty']:
        raise SyncError('difficulty_mismatch')
    if not opt.modifiers and any((opt.story, opt.passages, opt.checkpoints)):
        if guest.info['modifiers'] != host.info['modifiers'] or set(guest.info['modifier_tags']) != set(host.info['modifier_tags']):
            raise SyncError('modifiers_mismatch')


def is_passage_flag(k):
    return k.startswith('GameState.Flags.Quest.Door.')


def weapon_ability(k):
    return k.startswith(('Quest.PostLaunch.WeaponAbility.', 'GameState.Flags.Quest.PostLaunch.WeaponAbility.'))


def chosen_flag(k, opt, tag=False):
    if not tag and weapon_ability(k):
        return False
    base = story_tag(k) if tag else story_world(k)
    return base and (opt.passages if is_passage_flag(k) else opt.story)


def modifier_tag(k):
    return k.startswith(PREFIX) or k == MOD_ENABLED


def splice_selected(target, donor, pred):
    """Replace at first selected position; preserve every other entry and order."""
    incoming = [x for x in donor if pred(x[0])]
    result, inserted = [], False
    for x in target:
        if pred(x[0]):
            if not inserted:
                result.extend(incoming)
                inserted = True
        else:
            result.append(x)
    if not inserted:
        result.extend(incoming)
    require(len({x[0] for x in result}) == len(result), 'Duplicate merged key')
    return result


def swap_roots(b, replacements):
    root = root_properties(b)
    out = b
    for name, blob in sorted(replacements.items(), key=lambda kv:root[kv[0]]['start'], reverse=True):
        p = root[name]
        out = out[:p['start']] + blob + out[p['end']:]
    return struct.pack('<I', len(out)-4) + out[4:]


def serialization_patch(t, h, tr, hr, opt):
    ts, hs = children(t, tr['SerializationData']), children(h, hr['SerializationData'])
    changes, audit = {}, {}
    prefixes = (() if not opt.story else STORY_CLASSES) + (() if not opt.passages else PASSAGES) + (() if not opt.checkpoints else ANCHORS)
    for field, allowed in [('ObjectRecords', prefixes), ('ManualManagementObjectRecords', MANUAL_CLASSES if opt.story else ())]:
        if not allowed:
            continue
        tp, hp = children(t, ts[field])['Map'], children(h, hs[field])['Map']
        trec, hrec = parse_records(t, tp), parse_records(h, hp)
        selected = {r['guid'] for r in trec+hrec if r['class'].startswith(allowed)}
        for r in trec+hrec:
            require(r['guid'] not in selected or not r['class'] or r['class'].startswith(allowed), 'Conflicting actor classes for the same serialization ID')
        pairs = merge_items([(r['guid'], raw(t,r)) for r in trec], [(r['guid'], raw(h,r)) for r in hrec], lambda g:g in selected)
        changes[field] = replace_children(t, ts[field], {'Map':data_blob(t, tp, serialize_map([v for k,v in pairs]))})
        audit[field] = dict(selected=sorted(selected), from_host=sum(r['guid'] in selected for r in hrec), preserved=sum(r['guid'] not in selected for r in trec))
    if opt.checkpoints:
        tdm, hdm = dynamic_records(t, ts['DynamicObjectRecords']), dynamic_records(h, hs['DynamicObjectRecords'])
        tflat = [r for m in tdm for r in m['records']]
        hflat = [r for m in hdm for r in m['records']]
        tids = {r['guid'] for r in tflat if r['class'] in DYNAMIC_CLASSES}
        hids = {r['guid'] for r in hflat if r['class'] in DYNAMIC_CLASSES}
        hmaps = {m['name']:m for m in hdm}
        newmaps, done = [], set()
        for m in tdm+hdm:
            name = m['name']
            if name in done:
                continue
            done.add(name)
            tm, hm = next((x for x in tdm if x['name']==name),None), hmaps.get(name)
            preserved = [raw(t,r) for r in (tm['records'] if tm else []) if r['guid'] not in tids]
            copied = [raw(h,r) for r in (hm['records'] if hm else []) if r['guid'] in hids]
            if not tm and not copied:
                continue
            base, bb = (tm, t) if tm else (hm, h)
            mp = data_blob(bb, base['map'], serialize_map(preserved+copied))
            newmaps.append(bb[base['start']:base['value_start']] + mp + encode_fstr('None'))
        changes['DynamicObjectRecords'] = data_blob(t, ts['DynamicObjectRecords'], serialize_map(newmaps))
        treg, hreg = dynamic_registry(t, ts['DynamicObjectToMap']), dynamic_registry(h, hs['DynamicObjectToMap'])
        require(tids <= {r['guid'] for r in treg} and hids <= {r['guid'] for r in hreg}, 'Missing dynamic actor registry')
        require(not (({r['guid'] for r in treg}-tids) & hids), 'Dynamic actor ID collision')
        newreg = [raw(t,r) for r in treg if r['guid'] not in tids] + [raw(h,r) for r in hreg if r['guid'] in hids]
        changes['DynamicObjectToMap'] = data_blob(t, ts['DynamicObjectToMap'], serialize_map(newreg))
        audit['dynamic'] = dict(from_host=len(hids), preserved=len(tflat)-len(tids))
    return replace_children(t, tr['SerializationData'], changes), audit


def checkpoint_patch(t, h, tr, hr):
    changes = {name:raw(h,hr[name]) for name in ('LevelName','BoundAnchorName','PlayerTransform','LastVisitedArea')}
    name = 'ValidLocationTrackingComponentData'
    to, td, tp, _, _ = object_data(t,tr,name)
    ho, hd, hp, _, _ = object_data(h,hr,name)
    changes[name] = nested_replacement(t,[tr[name],to['ObjectRecordDetails'],tp],contents(h,hp))
    name = 'DualRealmDirectorData'
    to, td, tp, tdata, _ = object_data(t,tr,name)
    ho, hd, hp, hdata, _ = object_data(h,hr,name)
    for key in ('EnemySpawnerThatHasLanternLight','EnemyLanternLightVigorAmount'):
        if raw(t,tdata[key]) != raw(h,hdata[key]):
            raise SyncError('dropped_vigor')
    old, new = hd['PathName']['value'].encode(), td['PathName']['value'].encode()
    # No unsafe byte replacement when serialized FString lengths would change.
    if len(old) != len(new) or not old.isascii() or not new.isascii():
        raise SyncError('manager_layout')
    newdata = contents(h,hp).replace(old,new)
    newdeps = contents(h,ho['DependenciesValues']).replace(old,new)
    require(struct.unpack_from('<II',newdeps) == (0,1), 'Unsupported dependency group layout')
    host_owner, guest_owner = contents(h,hd['ID']), contents(t,td['ID'])
    require(len(host_owner)==len(guest_owner)==16 and newdeps[8:24]==host_owner, 'Invalid checkpoint dependency owner')
    newdeps = newdeps[:8] + guest_owner + newdeps[24:]
    declared = contents(h,hd['Dependencies']).replace(old,new)
    newdetails = replace_children(t,to['ObjectRecordDetails'], {'Data':data_blob(t,tp,newdata), 'Dependencies':data_blob(t,td['Dependencies'],declared)})
    changes[name] = replace_children(t,tr[name], {'ObjectRecordDetails':newdetails, 'DependenciesValues':data_blob(t,to['DependenciesValues'],newdeps)})
    return changes


def graph_audit(b):
    NATIVE_TAILS.clear()
    rows = [check_record(b,label,rec) for label,rec in all_records(b)]
    issues = [i for row in rows for i in row['issues']]
    root = root_properties(b)
    s = children(b,root['SerializationData'])
    ids = set()
    for cat in ('ObjectRecords','ManualManagementObjectRecords'):
        ids.update(r['guid'] for r in parse_records(b,children(b,s[cat])['Map']))
    dyn = [r for m in dynamic_records(b,s['DynamicObjectRecords']) for r in m['records']]
    ids.update(r['guid'] for r in dyn)
    reg = dynamic_registry(b,s['DynamicObjectToMap'])
    require(len(reg)==len({r['guid'] for r in reg}), 'Duplicate dynamic registry ID')
    require(len(dyn)==len({r['guid'] for r in dyn}), 'Duplicate dynamic actor ID')
    require({r['guid'] for r in dyn} <= {r['guid'] for r in reg}, 'Incomplete dynamic registry')
    for row in rows:
        for handle in row['handles']:
            if handle['guid'] != '0'*32 and handle['guid'] not in ids:
                issues.append(dict(type='missing_actor', record=row['record'], guid=handle['guid']))
    return dict(records=len(rows), components=sum(r['components'] for r in rows), issues=issues,
                opaque_native_tails=len(NATIVE_TAILS), native_tail_semantics_decoded=False)


def verify(t,h,n,opt,changes,serialaudit):
    tr,tw,tq,tg=locate(t);hr,hw,hq,hg=locate(h);nr,nw,nq,ng=locate(n)
    require(list(tr)==list(nr), 'Root property set changed')
    unchanged={}
    for name,p in tr.items():
        if name not in changes:
            require(raw(t,p)==raw(n,nr[name]), 'Protected root changed: '+name)
            unchanged[name]=sha(raw(t,p))
    for name in PROTECTED:
        require(name not in tr or name in unchanged, 'Personal data changed: '+name)
    # Every unselected world value and individual quest-tag entry is preserved.
    wp=lambda k:(opt.modifiers and k.startswith(PREFIX)) or chosen_flag(k,opt)
    gp=lambda k:(opt.modifiers and modifier_tag(k)) or chosen_flag(k,opt,True)
    wt,wh,wn=[json.loads(p['value']) for p in (tw,hw,nw)]
    for source,pred in [(wt,lambda k:not wp(k)),(wh,wp)]:
        require({k:v for k,v in source.items() if pred(k)}=={k:v for k,v in wn.items() if pred(k)}, 'World selection mismatch')
    for name,tp in children(t,tq).items():
        a=tag_entries(t,tp);bb=tag_entries(h,children(h,hq)[name]);c=tag_entries(n,children(n,nq)[name])
        # Modifier configuration is stored in GeneralTags only.
        pred=gp if name=='GeneralTags' else lambda k:chosen_flag(k,opt,True)
        require([x for x in a if not pred(x[0])]==[x for x in c if not pred(x[0])], 'Protected tags changed: '+name)
        safe_bb=splice_selected(bb,a,weapon_ability)
        require(dict(x for x in safe_bb if pred(x[0]))==dict(x for x in c if pred(x[0])), 'Selected tags mismatch: '+name)
        require([x for x in a if weapon_ability(x[0])]==[x for x in c if weapon_ability(x[0])], 'Personal weapon ability tags changed: '+name)
    ts,hs,ns=[children(b,r['SerializationData']) for b,r in [(t,tr),(h,hr),(n,nr)]]
    for field in ts:
        if field not in serialaudit and not (opt.checkpoints and field in ('DynamicObjectRecords','DynamicObjectToMap')):
            require(raw(t,ts[field])==raw(n,ns[field]), 'Unselected serialization field changed: '+field)
    for field in ('ObjectRecords','ManualManagementObjectRecords'):
        if field not in serialaudit:
            continue
        selected=set(serialaudit[field]['selected'])
        for buf,ss,take in [(t,ts,False),(h,hs,True)]:
            def selected_records(buf,ss):
                return {r['guid']:raw(buf,r) for r in parse_records(buf,children(buf,ss[field])['Map']) if (r['guid'] in selected)==take}
            require(selected_records(buf,ss)==selected_records(n,ns), 'Actor preservation mismatch: '+field)
    if opt.checkpoints:
        require(anchor_map(n)==anchor_map(h), 'Anchor state mismatch')
        for buf,ss,take in [(t,ts,False),(h,hs,True)]:
            def dynamic_selected(buf,ss):
                return {r['guid']:raw(buf,r) for m in dynamic_records(buf,ss['DynamicObjectRecords']) for r in m['records'] if (r['class'] in DYNAMIC_CLASSES)==take}
            require(dynamic_selected(buf,ss)==dynamic_selected(n,ns), 'Dynamic loot or anchor mismatch')
    restored=swap_roots(n,{name:raw(t,tr[name]) for name in changes})
    require(restored==t, 'Reverse patch failed')
    graph=graph_audit(n)
    require(not graph['issues'], 'Reference graph validation failed: '+json.dumps(graph['issues'][:4]))
    return dict(unchanged_root_sha256=unchanged, changed_root_properties=[k for k in tr if raw(t,tr[k])!=raw(n,nr[k])],
                inventory_byte_identical=True, stats_byte_identical=True, difficulty_and_ng_unchanged=True,
                unselected_world_and_tags_preserved=True, unselected_actors_preserved=True,
                reference_graph=graph, reverse_patch_identical=True)


def synchronize_payload(t,h,opt):
    tr,tw,tq,tg=locate(t);hr,hw,hq,hg=locate(h)
    wt,wh=json.loads(tw['value']),json.loads(hw['value'])
    pairs=list(wt.items())
    if opt.modifiers:
        pairs=splice_selected(pairs,list(wh.items()),lambda k:k.startswith(PREFIX))
    if opt.story or opt.passages:
        pairs=merge_items(pairs,list(wh.items()),lambda k:chosen_flag(k,opt))
    wnew=dict(pairs)
    changes={}
    if opt.modifiers or opt.story or opt.passages:
        world=replace_children(t,tr['WorldState'], {'WorldStateSavedData':data_blob(t,tw,encode_fstr(json.dumps(wnew,separators=(',',':'),ensure_ascii=False)))})
        changes['WorldState']=world
    tags={}
    qt,qh=children(t,tq),children(h,hq)
    require(list(qt)==list(qh), 'Quest list layout differs')
    for name,p in qt.items():
        pairs=tag_entries(t,p);hostpairs=tag_entries(h,qh[name])
        if opt.modifiers and name=='GeneralTags':
            # Preserve the enabled sentinel's position if its value already matches.
            if (MOD_ENABLED in [k for k,v in pairs]) == (MOD_ENABLED in [k for k,v in hostpairs]):
                pairs=splice_selected(pairs,hostpairs,lambda k:k.startswith(PREFIX))
            else:
                pairs=splice_selected(pairs,hostpairs,modifier_tag)
        if opt.story or opt.passages:
            # V4 places these tags in the story block. Keep that ordering but
            # always take their state from the guest, never from the donor.
            safe_hostpairs=splice_selected(hostpairs,pairs,weapon_ability)
            pairs=merge_items(pairs,safe_hostpairs,lambda k:chosen_flag(k,opt,True))
        tags[name]=data_blob(t,p,struct.pack('<I',len(pairs))+b''.join(v for k,v in pairs))
    qchanges={}
    if opt.modifiers or opt.story or opt.passages:
        qchanges['QuestsTags']=replace_children(t,tq,tags)
    if opt.checkpoints:
        qchanges['LastVisitedArea']=raw(h,children(h,hr['QuestDirectorSaveData'])['LastVisitedArea'])
    if qchanges:
        changes['QuestDirectorSaveData']=replace_children(t,tr['QuestDirectorSaveData'],qchanges)
    serialaudit={}
    if opt.story or opt.passages or opt.checkpoints:
        changes['SerializationData'],serialaudit=serialization_patch(t,h,tr,hr,opt)
    if opt.checkpoints:
        changes.update(checkpoint_patch(t,h,tr,hr))
    n=swap_roots(t,changes)
    audit=verify(t,h,n,opt,changes,serialaudit)
    audit['world_changes']=[dict(key=k,before=wt.get(k),after=wnew.get(k),before_present=k in wt,after_present=k in wnew) for k in sorted(wt.keys()|wnew.keys()) if (k in wt)!=(k in wnew) or wt.get(k)!=wnew.get(k)]
    audit['actors']=serialaudit
    return n,audit


def synchronize(guest,host,opt):
    check_pair(guest,host,opt)
    n,audit=synchronize_payload(guest.payload,host.payload,opt)
    result,preserved=rebuild(guest.header,guest.chunks,n)
    header,chunks,decoded=strict_read(result)
    require(header==guest.header and decoded==n, 'Output container verification failed')
    require(rebuild(header,chunks,decoded)[0]==result, 'Output round-trip failed')
    audit.update(input_sha256=sha(guest.data),output_sha256=sha(result),host_sha256=sha(host.data),
                 options=opt.keys(),crc_valid=True,unchanged_compressed_chunks=preserved)
    return result,audit
