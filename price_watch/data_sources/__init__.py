"""
データソースモジュール

各種データソースからのデータ取得インターフェース。
実際のAPI接続は将来実装。現時点ではインターフェース定義と
モックデータを提供する。
"""

from price_watch.data_sources.base import DataSourceBase
from price_watch.data_sources.government_data import GovernmentDataSource
from price_watch.data_sources.portal_tracker import PortalTracker

__all__ = [
    "DataSourceBase",
    "GovernmentDataSource",
    "PortalTracker",
]
