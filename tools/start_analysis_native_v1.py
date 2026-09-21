"""Explicit operator launcher. Import/help never arms a reader or native exporter."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Local ANALYSIS ONLY native tail; no execution authority.')
    parser.add_argument('--start-analysis-only', action='store_true', required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--installed-exporter', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--dashboard-origin', default='http://localhost:3000')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('local port must be between 1024 and 65535')
    from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1, WindowsQpc, local_path
    from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
    import uvicorn
    folder = local_path(args.output_directory)
    folder.mkdir(parents=True, exist_ok=True)
    adapter = FreshNativeAdapterV1(directory=folder, installed_exporter=args.installed_exporter, qpc_clock=WindowsQpc())
    try:
        adapter.poll()
        if adapter.status in ('REVOKED', 'DISCONNECTED'):
            raise ValueError('ADAPTER_PREFLIGHT_FAILED')
        print('ANALYSIS_ONLY=YES PAPER_ENTRIES=DISABLED SIM=DISABLED LIVE=NO', flush=True)
        print('ADAPTER_STATUS='+adapter.status, flush=True)
        uvicorn.run(create_market_analysis_time_app_v1(adapter=adapter, dashboard_origin=args.dashboard_origin),
                    host='127.0.0.1', port=args.port, workers=1, access_log=False)
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
