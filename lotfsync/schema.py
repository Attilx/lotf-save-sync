import struct
from .format import *
from .properties import properties, fstr
from .errors import FormatError
STORY_PARTS = {'NPC', 'Boss', 'BossMemberBerry', 'FirstBossKilled', 'FirstMemberBerry', 'Kill', 'GameState', 'Beacon', 'Ending', 'Castle', 'Door', 'Fix', 'ReachLocation', 'RequireQuestState', 'GiveItem', 'ActivateStigma', 'PostLaunch', 'Grove', 'ParasiteColumn', 'Rosary', 'Shrine', 'Journal', 'JournalPage', 'BellBoyFigurines'}
PROTECTED_WORLD_PREFIXES = ('GameState.Flags.Quest.PostLaunch.WeaponAbility.',)
CLASS_PREFIXES = ('/Game/Placeables/Progression/', '/Game/Placeables/Elevator/', '/Game/Placeables/BossGate/', '/Game/Placeables/Quests/Stigmas/', '/Game/Blueprints/AI/Utility/Core/Actors/EnemySpawners/Bosses/', '/Game/Blueprints/AI/Utility/Core/Actors/EnemySpawners/MiniBosses/', '/Game/Blueprints/AI/Utility/Core/Actors/NpcSpawners/', '/Game/Blueprints/Data/Character/Enemies/Bosses/Core/', '/Game/Blueprints/DualRealmSubsystem/DualRealmAnchor_')
DYNAMIC_CLASSES = {'/Script/LOTF2.LOTF2PlayerStartTeleportDynamic', '/Game/Blueprints/DualRealmSubsystem/DualRealmForgedAnchorActor_BP.DualRealmForgedAnchorActor_BP_C'}

def story_world(k):
    if k.lower().startswith(('gamestate.boss.replayboss.', 'gamestate.boss.bossrush.')):
        return False
    if k.startswith(PROTECTED_WORLD_PREFIXES):
        return False
    p = 'GameState.Flags.Quest.'
    if k.startswith(p):
        return k[len(p):].split('.')[0] in STORY_PARTS
    return k.startswith('Quest.PostLaunch.') or k.lower().startswith('gamestate.boss.')

def story_tag(k):
    if story_world(k):
        return True
    lo = k.lower()
    if lo.startswith(('gamestate.boss.replayboss.', 'gamestate.boss.bossrush.')):
        return False
    if lo.startswith(('gamestate.boss.', 'gamestate.miniboss.', 'gamestate.npc.', 'gamestate.cinematics.', 'story.stigma.', 'boss.bossarea.', 'character.npc.', 'character.enemy.')):
        return True
    if k.startswith('Quest.PostLaunch.WeaponAbility.'):
        return False
    return k.startswith(('Quest.Location.', 'Quest.Beacon.', 'Quest.Ending.', 'Quest.Boss.', 'Quest.Interaction.', 'Quest.Castle.', 'Quest.Grove.', 'Quest.Rosary.', 'Quest.BellBoyFigurine.', 'Quest.PostLaunch.'))

def raw(b, p):
    return b[p['start']:p['end']]

def contents(b, p):
    return b[p['data_start']:p['end']]

def replace_children(b, parent, replacements):
    old = children(b, parent)
    if not set(replacements) <= set(old):
        raise FormatError('Unexpected save structure')
    return data_blob(b, parent, b''.join((replacements.get(n, raw(b, p)) for n, p in old.items())) + encode_fstr('None'))

def merge_items(target, donor, predicate):
    """Deterministic, idempotent, preserving all unselected entries and order."""
    target_keep = [x for x in target if not predicate(x[0])]
    donor_take = [x for x in donor if predicate(x[0])]
    result = target_keep + donor_take
    if not len({x[0] for x in result}) == len(result):
        raise FormatError('Unexpected save structure')
    return result

def object_data(b, root, name):
    obj = children(b, root[name])
    details = children(b, obj['ObjectRecordDetails'])
    p = details['Data']
    if not (p['type'] == 'ArrayProperty' and p['subtype'] == 'ByteProperty'):
        raise FormatError('Unexpected save structure')
    if not struct.unpack_from('<I', b, p['data_start'])[0] == p['size'] - 4:
        raise FormatError('Unexpected save structure')
    pp, end = properties(b, p['data_start'] + 4, p['end'])
    if not b[end:p['end']] in (b'\x00' * 4, b'\x00' * 8):
        raise FormatError('Unexpected save structure')
    return (obj, details, p, {x['name']: x for x in pp}, b[end:p['end']])

def anchor_map(b):
    root = root_properties(b)
    _, _, _, data, _ = object_data(b, root, 'DualRealmDirectorData')
    p = data['AnchorTeleportPointActivationMap']
    pos = p['data_start']
    removed, n = struct.unpack_from('<II', b, pos)
    if not not removed:
        raise FormatError('Unexpected save structure')
    pos += 8
    result = {}
    for _ in range(n):
        name, pos = fstr(b, pos)
        result[name] = b[pos]
        pos += 1
    if not pos == p['end']:
        raise FormatError('Unexpected save structure')
    return result

def serialize_map(entries):
    return struct.pack('<II', 0, len(entries)) + b''.join(entries)
