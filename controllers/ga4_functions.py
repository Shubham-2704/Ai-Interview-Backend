import os
import json
from datetime import datetime, timedelta, date
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account


# Global variables
_ga4_client = None
_executor = ThreadPoolExecutor(max_workers=5)

# ==================== INITIALIZATION ====================
def initialize_ga4_client():
    """Initialize GA4 client once"""
    global _ga4_client
    
    try:
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            print("⚠️ GA4_PROPERTY_ID not set in environment")
            return None
        
        # Try environment variable first
        creds_json = os.getenv("GA4_CREDENTIALS_JSON")
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
                print("✅ Using GA4 credentials from environment variable")
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in GA4_CREDENTIALS_JSON: {e}")
                return None
        
        # Try file path
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            # Try with .json extension if not present
            if not credentials_path.endswith('.json') and os.path.exists(credentials_path + '.json'):
                credentials_path = credentials_path + '.json'
            
            if os.path.exists(credentials_path):
                try:
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path,
                        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                    )
                    print(f"✅ Using GA4 credentials from file: {credentials_path}")
                except Exception as e:
                    print(f"❌ Error reading credentials file {credentials_path}: {e}")
                    return None
            else:
                print(f"❌ Credentials file not found: {credentials_path}")
                return None
        else:
            print("❌ No Google Analytics credentials found")
            print("   Please set either GA4_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS")
            return None
        
        # Initialize client
        _ga4_client = BetaAnalyticsDataClient(credentials=credentials)
        print(f"✅ GA4 Client initialized successfully for property: {property_id}")
        return _ga4_client
        
    except Exception as e:
        print(f"❌ Failed to initialize GA4 client: {e}")
        return None
    
def get_ga4_client():
    """Get or initialize GA4 client"""
    global _ga4_client
    if _ga4_client is None:
        _ga4_client = initialize_ga4_client()
    return _ga4_client

# ==================== HELPER FUNCTIONS ====================
def get_date_range(time_range: str = "7d"):
    """Convert time range to date strings"""
    today = date.today()
    
    if time_range == "24h":
        start_date = (today - timedelta(days=1)).isoformat()
    elif time_range == "7d":
        start_date = (today - timedelta(days=7)).isoformat()
    elif time_range == "30d":
        start_date = (today - timedelta(days=30)).isoformat()
    elif time_range == "90d":
        start_date = (today - timedelta(days=90)).isoformat()
    elif time_range == "today":
        start_date = today.isoformat()
    elif time_range == "yesterday":
        start_date = end_date = (today - timedelta(days=1)).isoformat()
        return start_date, end_date
    else:
        start_date = (today - timedelta(days=7)).isoformat()
    
    end_date = today.isoformat()
    return start_date, end_date

# ==================== CORE GA4 FUNCTIONS ====================
async def get_realtime_metrics():
    """Get LIVE real-time user metrics"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_realtime()
        
        from google.analytics.data_v1beta.types import (
            RunRealtimeReportRequest, Metric, Dimension
        )
        
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_realtime()
        
        request = RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="activeUsers")],
            dimensions=[
                Dimension(name="country"),
                Dimension(name="deviceCategory"),
                Dimension(name="platform")
            ],
            limit=20
        )
        
        # Run in thread pool (GA4 client is sync)
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_realtime_report, request
        )
        
        # Parse response
        active_users = 0
        countries = []
        devices = []
        
        for row in response.rows:
            metric_value = int(row.metric_values[0].value) if row.metric_values else 0
            active_users += metric_value
            
            country = row.dimension_values[0].value if len(row.dimension_values) > 0 else "unknown"
            device = row.dimension_values[1].value if len(row.dimension_values) > 1 else "unknown"
            platform = row.dimension_values[2].value if len(row.dimension_values) > 2 else "unknown"
            
            if country and country != "(not set)":
                countries.append({"country": country, "users": metric_value})
            if device:
                devices.append({"device": device, "platform": platform, "users": metric_value})
        
        result = {
            "activeUsers": active_users,
            "countries": sorted(countries, key=lambda x: x["users"], reverse=True)[:10],
            "devices": devices,
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting realtime metrics: {e}")
        return get_empty_realtime()

async def get_overview_metrics(time_range: str = "7d"):
    """Get LIVE overview metrics"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_overview(time_range)
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_overview(time_range)
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="engagedSessions"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
                Metric(name="newUsers"),
                Metric(name="eventCount")
            ],
            dimensions=[Dimension(name="date")],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))]
        )
        
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, request
        )
        
        # Calculate totals
        totals = {
            "totalUsers": 0,
            "sessions": 0,
            "pageviews": 0,
            "engagedSessions": 0,
            "averageDuration": 0,
            "bounceRate": 0,
            "newUsers": 0,
            "events": 0
        }
        
        daily_data = []
        
        for row in response.rows:
            date_str = row.dimension_values[0].value
            users = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            pageviews = int(row.metric_values[2].value)
            engaged = int(row.metric_values[3].value)
            duration = float(row.metric_values[4].value)
            bounce = float(row.metric_values[5].value)
            new_users = int(row.metric_values[6].value)
            events = int(row.metric_values[7].value)
            
            totals["totalUsers"] += users
            totals["sessions"] += sessions
            totals["pageviews"] += pageviews
            totals["engagedSessions"] += engaged
            totals["averageDuration"] += duration
            totals["bounceRate"] += bounce
            totals["newUsers"] += new_users
            totals["events"] += events
            
            daily_data.append({
                "date": date_str,
                "users": users,
                "sessions": sessions,
                "pageviews": pageviews,
                "engagedSessions": engaged
            })
        
        # Calculate averages
        if len(daily_data) > 0:
            totals["averageDuration"] = totals["averageDuration"] / len(daily_data)
            totals["bounceRate"] = totals["bounceRate"] / len(daily_data)
        
        result = {
            "totals": totals,
            "dailyData": daily_data,
            "timeRange": time_range,
            "startDate": start_date,
            "endDate": end_date,
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting overview metrics: {e}")
        return get_empty_overview(time_range)

async def get_user_acquisition(time_range: str = "30d"):
    """Get LIVE user acquisition channels"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_acquisition()
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_acquisition()
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),
                Metric(name="newUsers"),
                Metric(name="sessions"),
                Metric(name="engagedSessions")
            ],
            dimensions=[
                Dimension(name="sessionDefaultChannelGroup"),
                Dimension(name="firstUserSource"),
                Dimension(name="firstUserMedium")
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="totalUsers"),
                desc=True
            )],
            limit=15
        )
        
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, request
        )
        
        channels = []
        sources = []
        
        for row in response.rows:
            channel = row.dimension_values[0].value or "Direct"
            source = row.dimension_values[1].value or "direct"
            medium = row.dimension_values[2].value or "(none)"
            users = int(row.metric_values[0].value)
            new_users = int(row.metric_values[1].value)
            sessions = int(row.metric_values[2].value)
            engaged = int(row.metric_values[3].value)
            
            channels.append({
                "channel": channel,
                "users": users,
                "newUsers": new_users,
                "sessions": sessions,
                "engagedSessions": engaged
            })
            
            sources.append({
                "source": source,
                "medium": medium,
                "users": users
            })
        
        result = {
            "channels": channels,
            "sources": sources,
            "totalChannels": len(channels),
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting user acquisition: {e}")
        return get_empty_acquisition()

async def get_page_performance(time_range: str = "7d"):
    """Get LIVE top performing pages"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_pages()
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_pages()
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="totalUsers"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
                Metric(name="eventCount")
            ],
            dimensions=[
                Dimension(name="pageTitle"),
                Dimension(name="pagePath"),
                Dimension(name="country")
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True
            )],
            limit=20
        )
        
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, request
        )
        
        pages = []
        
        for row in response.rows:
            title = row.dimension_values[0].value or "Unknown Page"
            path = row.dimension_values[1].value or "/"
            country = row.dimension_values[2].value or "Unknown"
            views = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            duration = float(row.metric_values[2].value)
            bounce = float(row.metric_values[3].value)
            events = int(row.metric_values[4].value)
            
            pages.append({
                "title": title[:50] + "..." if len(title) > 50 else title,
                "path": path,
                "country": country,
                "views": views,
                "users": users,
                "avgDuration": round(duration, 1),
                "bounceRate": round(bounce, 1),
                "events": events
            })
        
        result = {
            "pages": pages,
            "totalPages": len(pages),
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting page performance: {e}")
        return get_empty_pages()

async def get_geographic_data(time_range: str = "30d"):
    """Get LIVE geographic distribution"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_geo()
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_geo()
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews")
            ],
            dimensions=[
                Dimension(name="country"),
                Dimension(name="city"),
                Dimension(name="region")
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="totalUsers"),
                desc=True
            )],
            limit=50
        )
        
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, request
        )
        
        countries = []
        cities = []
        
        for row in response.rows:
            country = row.dimension_values[0].value or "Unknown"
            city = row.dimension_values[1].value or "Unknown"
            region = row.dimension_values[2].value or "Unknown"
            users = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            views = int(row.metric_values[2].value)
            
            if country != "Unknown":
                countries.append({
                    "country": country,
                    "users": users,
                    "sessions": sessions,
                    "pageviews": views
                })
            
            if city != "Unknown":
                cities.append({
                    "city": city,
                    "region": region,
                    "country": country,
                    "users": users
                })
        
        result = {
            "countries": countries[:20],
            "cities": cities[:20],
            "totalCountries": len(countries),
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting geographic data: {e}")
        return get_empty_geo()

async def get_device_data(time_range: str = "30d"):
    """Get LIVE device and browser data - UNIQUE USERS"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_devices()
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_devices()
        
        # CHANGE 1: Query 1 - Get UNIQUE device users (grouped by device only)
        device_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),  # UNIQUE users per device
                Metric(name="sessions"),
                Metric(name="averageSessionDuration")
            ],
            dimensions=[
                Dimension(name="deviceCategory"),  # Only device, no browser/OS
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="totalUsers"),
                desc=True
            )],
            limit=10
        )
        
        device_response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, device_request
        )
        
        devices = []
        
        for row in device_response.rows:
            device = row.dimension_values[0].value or "Unknown"
            unique_users = int(row.metric_values[0].value)  # UNIQUE users
            sessions = int(row.metric_values[1].value)
            duration = float(row.metric_values[2].value)
            
            # CHANGE 2: Group by device only (not device+browser+OS combo)
            devices.append({
                "device": device,
                "users": unique_users,  # This is UNIQUE count
                "sessions": sessions,
                "avgDuration": round(duration, 1)
            })
        
        # CHANGE 3: Query 2 - Get browser data separately
        browser_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),  # UNIQUE users per browser
            ],
            dimensions=[
                Dimension(name="browser"),
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="totalUsers"),
                desc=True
            )],
            limit=10
        )
        
        browser_response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, browser_request
        )
        
        browsers = []
        
        for row in browser_response.rows:
            browser = row.dimension_values[0].value or "Unknown"
            unique_users = int(row.metric_values[0].value)
            
            browsers.append({
                "browser": browser,
                "users": unique_users  # UNIQUE count
            })
        
        # CHANGE 4: Query 3 - Get OS data separately
        os_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="totalUsers"),  # UNIQUE users per OS
            ],
            dimensions=[
                Dimension(name="operatingSystem"),
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="totalUsers"),
                desc=True
            )],
            limit=10
        )
        
        os_response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, os_request
        )
        
        operating_systems = []
        
        for row in os_response.rows:
            os_name = row.dimension_values[0].value or "Unknown"
            unique_users = int(row.metric_values[0].value)
            
            operating_systems.append({
                "os": os_name,
                "users": unique_users  # UNIQUE count
            })
        
        result = {
            "devices": devices,
            "browsers": browsers[:10],
            "operatingSystems": operating_systems[:10],
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting device data: {e}")
        return get_empty_devices()
    
async def get_events_data(time_range: str = "7d"):
    """Get LIVE events tracking data"""
    try:
        client = get_ga4_client()
        if not client:
            return get_empty_events()
        
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Metric, Dimension, OrderBy
        )
        
        start_date, end_date = get_date_range(time_range)
        property_id = os.getenv("GA4_PROPERTY_ID")
        if property_id and property_id.startswith("properties/"):
            property_id = property_id.replace("properties/", "")
        
        if not property_id:
            return get_empty_events()
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="eventCount"),
                Metric(name="totalUsers")
            ],
            dimensions=[
                Dimension(name="eventName"),
                Dimension(name="pagePath")
            ],
            order_bys=[OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="eventCount"),
                desc=True
            )],
            limit=25
        )
        
        response = await asyncio.get_event_loop().run_in_executor(
            _executor, client.run_report, request
        )
        
        events = []
        
        for row in response.rows:
            event_name = row.dimension_values[0].value or "Unknown"
            page_path = row.dimension_values[1].value or "/"
            count = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            
            events.append({
                "name": event_name,
                "page": page_path,
                "count": count,
                "users": users
            })
        
        result = {
            "events": events,
            "totalEvents": sum(e["count"] for e in events),
            "uniqueEvents": len(events),
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": True
        }
        
        return result
        
    except Exception as e:
        print(f"Error getting events data: {e}")
        return get_empty_events()

# ==================== EMPTY DATA FUNCTIONS ====================
def get_empty_realtime():
    """Return empty realtime data"""
    return {
        "activeUsers": 0,
        "countries": [],
        "devices": [],
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_overview(time_range="7d"):
    """Return empty overview data"""
    days = 7 if time_range == "7d" else 30 if time_range == "30d" else 90
    start_date = (date.today() - timedelta(days=days)).isoformat()
    
    return {
        "totals": {
            "totalUsers": 0,
            "sessions": 0,
            "pageviews": 0,
            "engagedSessions": 0,
            "averageDuration": 0,
            "bounceRate": 0,
            "newUsers": 0,
            "events": 0
        },
        "dailyData": [],
        "timeRange": time_range,
        "startDate": start_date,
        "endDate": date.today().isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_acquisition():
    return {
        "channels": [],
        "sources": [],
        "totalChannels": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_pages():
    return {
        "pages": [],
        "totalPages": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_geo():
    return {
        "countries": [],
        "cities": [],
        "totalCountries": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_devices():
    return {
        "devices": [],
        "browsers": [],
        "operatingSystems": [],
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

def get_empty_events():
    return {
        "events": [],
        "totalEvents": 0,
        "uniqueEvents": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": False,
        "error": "GA4 connection failed"
    }

# ==================== BATCH FUNCTIONS ====================
async def get_all_analytics(time_range: str = "7d"):
    """Get all analytics data in one call - ALWAYS LIVE"""
    try:
        # Run all analytics functions concurrently
        results = await asyncio.gather(
            get_overview_metrics(time_range),
            get_realtime_metrics(),
            get_user_acquisition(time_range),
            get_page_performance(time_range),
            get_geographic_data(time_range),
            get_device_data(time_range),
            get_events_data(time_range),
            return_exceptions=True
        )
        
        # Handle any exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Error in analytics function: {result}")
                processed_results.append({})
            else:
                processed_results.append(result)
        
        return {
            "status": "success",
            "data": {
                "overview": processed_results[0],
                "realtime": processed_results[1],
                "acquisition": processed_results[2],
                "pages": processed_results[3],
                "geographic": processed_results[4],
                "devices": processed_results[5],
                "events": processed_results[6],
                "timestamp": datetime.utcnow().isoformat(),
                "is_live": True
            }
        }
        
    except Exception as e:
        print(f"Error getting all analytics: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {},
            "is_live": False
        }

