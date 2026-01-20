from typing import Dict
from controllers import ga4_functions

async def get_dashboard_data(time_range: str = "7d") -> Dict:
    """Get complete analytics dashboard data"""
    try:
        data = await ga4_functions.get_all_analytics(time_range)
        return data
    except Exception as e:
        print(f"Error in get_dashboard_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {},
            "is_live": False  # ADD THIS
        }

async def get_overview_data(time_range: str = "7d") -> Dict:
    """Get overview metrics"""
    try:
        data = await ga4_functions.get_overview_metrics(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_overview_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_realtime_data() -> Dict:
    """Get real-time analytics"""
    try:
        data = await ga4_functions.get_realtime_metrics()
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_realtime_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_acquisition_data(time_range: str = "30d") -> Dict:
    """Get user acquisition channels"""
    try:
        data = await ga4_functions.get_user_acquisition(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_acquisition_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_pages_data(time_range: str = "7d") -> Dict:
    """Get page performance data"""
    try:
        data = await ga4_functions.get_page_performance(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_pages_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_geographic_data(time_range: str = "30d") -> Dict:
    """Get geographic distribution"""
    try:
        data = await ga4_functions.get_geographic_data(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_geographic_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_devices_data(time_range: str = "30d") -> Dict:
    """Get device and browser analytics"""
    try:
        data = await ga4_functions.get_device_data(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_devices_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }

async def get_events_data(time_range: str = "7d") -> Dict:
    """Get events analytics"""
    try:
        data = await ga4_functions.get_events_data(time_range)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        print(f"Error in get_events_data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }
