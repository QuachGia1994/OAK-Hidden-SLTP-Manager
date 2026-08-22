from pathlib import Path

EA = (Path(__file__).resolve().parents[1] / "mt5" / "OAK_Cloud_Manager_EA.mq5").read_text(encoding="utf-8")


def test_ea_uses_existing_cloud_mailbox_and_identity_binding():
    assert 'oak:mt5:bridge:task:v1:' in EA
    assert 'oak:mt5:bridge:queue:v1:' in EA
    assert 'oak:mt5:bridge:arbiter:v1:' in EA
    assert 'oak:mt5:bridge:heartbeat:v1:' in EA
    assert 'InpExpectedLogin' in EA
    assert '\\"runtime\\":\\"mql5-ea\\"' in EA
    assert 'RedisSet(ArbiterKey(task_id),claim_token,OAK_TASK_TTL,true,claim_result)' in EA


def test_ea_covers_account_management_features_without_python_runtime():
    for marker in (
        'PreEntryNet',
        'EnsureSelectedProtection',
        'InpBreakEvenAtR',
        'InpCloseAtR',
        'InpPartialRLevels',
        'ExecutePartialTask',
        'pp_threshold',
        'POSITION_IDENTIFIER',
    ):
        assert marker in EA
    assert 'PositionClosePartial' not in EA
    assert 'req.action=TRADE_ACTION_DEAL;' in EA
    assert 'WebRequest(' in EA
    assert 'MetaTrader5' not in EA


def test_ea_action_router_supports_cloud_and_dynamic_partial_actions():
    for action in ('positions', 'entry', 'close', 'modify', 'partial'):
        assert f'action=="{action}"' in EA
    assert 'StateSet(id,"pp_armed",1.0)' in EA
    assert 'mode=="profit"?1.0:2.0' in EA


def test_ea_has_no_known_conversion_signature_mismatches():
    assert 'LongToString' not in EA
    assert 'IntegerToString' in EA
    assert 'StringToCharArray(body, data' not in EA
    assert 'CharArrayToString(result' not in EA
    assert 'Utf8ToHttpBytes' in EA
    assert 'HttpBytesToUtf8' in EA
    assert 'const char &input[]' not in EA
    assert 'ShortToString(8)' in EA
    assert 'ShortToString(12)' in EA


def test_ea_retries_result_upload_without_replaying_broker_mutation():
    assert 'PersistFinalTask' in EA
    assert 'FlushPendingFinalTask' in EA
    assert 'broker mutation will NOT be replayed' in EA
