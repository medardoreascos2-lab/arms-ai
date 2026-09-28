"""Read-only first-operation readiness; never admission or human authorization."""
from backend.services.sim_native_economic_news_authority_v1 import SimNativeEconomicNewsLifecycleV1


def news_fields(value):
    return {'economic_news_'+key:value.get(key) for key in ('status','reason','covered','blocked',
        'package_age_seconds','coverage_start','coverage_end','expires_us','next_event_us')}


class FirstControlledTradePreflightV3:
    def __init__(self, *, evidence, read_financial, read_news=None):
        self._evidence = evidence
        self._read_financial = read_financial
        self._read_news = read_news or SimNativeEconomicNewsLifecycleV1.unavailable

    @staticmethod
    def unavailable():
        result = dict.fromkeys(("backend_account_id", "native_account", "provider", "instrument",
            "physical_test_readiness", "position_state", "active_order_count", "controlled_v3_configured",
            "config_signature_valid", "config_expired", "reconciliation_fence", "financial_status",
            "open_position_count", "closed_position_count", "journal_count", "pending_dashboard_events",
            "risk_profile", "risk_version", "commissioning_policy_id", "native_submit_enabled",
            "auto_retry_allowed", "controlled_observation_only"))
        result.update(execution_domain="SIM_NATIVE", status="NOT_READY", reason="FINANCIAL_OWNER_UNAVAILABLE",
                      heartbeat_fresh=False, config_valid=False, risk_version_match=False, policy_id_match=False,
                      authorization_state="NOT_AUTHORIZED", quantity_limit=1)
        result.update(news_fields(SimNativeEconomicNewsLifecycleV1.unavailable()))
        return result

    def get_snapshot(self):
        result, _ = self._evidence.inspect()
        result.update(status="NOT_READY", authorization_state="NOT_AUTHORIZED", quantity_limit=1)
        financial = self._read_financial()
        result["financial_status"] = financial.get("status")
        for key in ("open_position_count", "closed_position_count", "journal_count", "pending_dashboard_events"):
            result[key] = financial.get(key)
        news = self._read_news()
        result.update(news_fields(news))
        if result["reason"] is not None:
            return result
        if (financial.get("execution_domain") != "SIM_NATIVE"
                or financial.get("backend_account_id") != result["backend_account_id"]
                or financial.get("native_account") != result["native_account"]
                or financial.get("provider") != result["provider"]
                or financial.get("instrument") != result["instrument"]
                or type(financial.get("runtime_generation")) is not int or financial["runtime_generation"] != 1
                or financial.get("status") != "NO_OPERATION"
                or any(type(result[key]) is not int or result[key] != 0 for key in
                       ("open_position_count", "closed_position_count", "journal_count", "pending_dashboard_events"))):
            result["reason"] = "FINANCIAL_NOT_QUIESCENT"
            return result
        if news.get('status') != 'CERTIFIED_CLEAR' or news.get('covered') is not True or news.get('blocked') is not False:
            result['reason'] = 'ECONOMIC_NEWS_NOT_READY'
            return result
        result["status"] = "READY_FOR_AUTHORIZATION"
        return result
