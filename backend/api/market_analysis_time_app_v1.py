"""Explicit read-only dashboard app. No accounts, PAPER runtime or feed startup."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.market_data.analysis_time_profile_v1 import MarketAnalysisTimeProfileV1


def create_market_analysis_time_app_v1(*, profile, dashboard_origin='http://localhost:3000'):
    if type(profile) is not MarketAnalysisTimeProfileV1:
        raise TypeError('explicit analysis-only profile required')
    app=FastAPI(title='ARMS source-relative market observations',docs_url=None,redoc_url=None)
    app.add_middleware(CORSMiddleware,allow_origins=[dashboard_origin],allow_methods=['GET'],allow_headers=['Accept'])

    @app.get('/api/v2/market-analysis/time-profile')
    def snapshot():
        return profile.snapshot()

    return app
