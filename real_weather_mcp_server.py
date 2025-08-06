#!/usr/bin/env python3
"""
真实天气查询MCP服务器
Real Weather Query MCP Server
支持多个天气API服务
"""

import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
import uvicorn
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('weather_mcp_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Weather MCP Server",
    description="真实天气查询MCP服务器，支持多个天气API",
    version="1.0.0"
)

# 配置多个天气API服务
WEATHER_APIS = {
    "openweather": {
        "base_url": "https://api.openweathermap.org/data/2.5",
        "api_key": "f8c2e6b4a5d3c7e9f1a2b3c4d5e6f7g8",  # 更新的OpenWeather API Key
        "param_name": "appid"
    },
    "weatherapi": {
        "base_url": "https://api.weatherapi.com/v1",
        "api_key": "18ccb142720b4a449d9122550250608",  # WeatherAPI密钥保持不变
        "param_name": "key"
    }
}

# 默认使用的API服务
DEFAULT_API = "weatherapi"

class MCPRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class MCPResponse(BaseModel):
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

# MCP工具定义
WEATHER_TOOLS = [
    {
        "name": "get_current_weather",
        "description": "获取指定城市的当前天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如 'Beijing' 或 'New York'"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "default": "metric",
                    "description": "温度单位: metric(摄氏度), imperial(华氏度), kelvin(开尔文)"
                },
                "api_service": {
                    "type": "string",
                    "enum": ["openweather", "weatherapi"],
                    "default": DEFAULT_API,
                    "description": "使用的天气API服务"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "获取指定城市的天气预报",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7,
                    "default": 3,
                    "description": "预报天数 (1-7天)"
                },
                "api_service": {
                    "type": "string",
                    "enum": ["openweather", "weatherapi"],
                    "default": DEFAULT_API,
                    "description": "使用的天气API服务"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_city",
        "description": "搜索城市信息",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "返回结果数量"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_air_quality",
        "description": "获取空气质量指数",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                },
                "api_service": {
                    "type": "string",
                    "enum": ["openweather", "weatherapi"],
                    "default": DEFAULT_API
                }
            },
            "required": ["city"]
        }
    }
]

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "Real Weather MCP Server",
        "version": "1.0.0",
        "supported_apis": list(WEATHER_APIS.keys()),
        "tools_count": len(WEATHER_TOOLS)
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    # 测试API连接
    api_status = {}
    for api_name, config in WEATHER_APIS.items():
        try:
            async with httpx.AsyncClient() as client:
                # 简单的连通性测试
                test_url = config["base_url"]
                if api_name == "openweather":
                    test_url += f"/weather?q=London&{config['param_name']}={config['api_key']}"
                elif api_name == "weatherapi":
                    test_url += f"/current.json?{config['param_name']}={config['api_key']}&q=London"
                
                response = await client.get(test_url, timeout=5)
                api_status[api_name] = "healthy" if response.status_code == 200 else "error"
        except:
            api_status[api_name] = "unreachable"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "apis": api_status
    }

@app.get("/mcp/tools")
async def get_tools():
    """获取工具列表"""
    return {"tools": WEATHER_TOOLS}

@app.get("/tools")
async def get_tools_standard():
    """获取工具列表 - 标准格式"""
    return {"tools": WEATHER_TOOLS}

@app.post("/mcp/tools/call")
async def call_tool_standard(request: Dict[str, Any], http_request: Request):
    """调用工具 - 标准MCP端点"""
    return await handle_tool_call(request, http_request)

@app.post("/call")
async def call_tool_compatible(request: Dict[str, Any], http_request: Request):
    """调用工具 - 兼容端点（用于database_mcp_service调用）"""
    logger.info(f"[MCP-SERVER] 收到兼容端点调用: /call")
    
    # 转换请求格式：database_mcp_service发送的是{"tool": "name", "arguments": {...}}
    # 需要转换为标准格式 {"name": "tool_name", "arguments": {...}}
    if "tool" in request:
        converted_request = {
            "name": request["tool"],
            "arguments": request.get("arguments", {})
        }
        logger.info(f"   - 转换请求格式: {request} -> {converted_request}")
        return await handle_tool_call(converted_request, http_request)
    else:
        # 如果已经是标准格式，直接处理
        return await handle_tool_call(request, http_request)

async def handle_tool_call(request: Dict[str, Any], http_request: Request):
    """统一的工具调用处理逻辑"""
    # 记录详细的请求信息
    client_host = http_request.client.host if http_request.client else "unknown"
    logger.info(f"[MCP-SERVER] 收到工具调用请求")
    logger.info(f"   - 客户端IP: {client_host}")
    logger.info(f"   - 请求时间: {datetime.now().isoformat()}")
    logger.info(f"   - 请求头: {dict(http_request.headers)}")
    logger.info(f"   - 请求体类型: {type(request)}")
    logger.info(f"   - 请求体大小: {len(str(request))} 字符")
    logger.info(f"   - 请求体内容: {request}")
    
    tool_name = request.get("name")
    arguments = request.get("arguments", {})
    
    logger.info(f"[TOOL-CALL] 解析工具调用")
    logger.info(f"   - 工具名称: {tool_name}")
    logger.info(f"   - 参数类型: {type(arguments)}")
    logger.info(f"   - 参数内容: {arguments}")
    
    try:
        result = await execute_weather_tool(tool_name, arguments)
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"[TOOL-CALL] 工具调用失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/mcp")
async def mcp_handler(request: MCPRequest):
    """MCP协议主处理端点"""
    method = request.method
    params = request.params or {}
    request_id = request.id
    
    try:
        if method == "initialize":
            return MCPResponse(
                result={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {
                        "name": "weather-mcp-server",
                        "version": "1.0.0"
                    }
                },
                id=request_id
            )
        elif method == "tools/list":
            return MCPResponse(
                result={"tools": WEATHER_TOOLS},
                id=request_id
            )
        elif method == "tools/call":
            tool_result = await execute_weather_tool(
                params.get("name"),
                params.get("arguments", {})
            )
            return MCPResponse(
                result={
                    "content": [{"type": "text", "text": tool_result}],
                    "isError": False
                },
                id=request_id
            )
        else:
            return MCPResponse(
                error={"code": -32601, "message": f"Method not found: {method}"},
                id=request_id
            )
    except Exception as e:
        return MCPResponse(
            error={"code": -32603, "message": f"Internal error: {str(e)}"},
            id=request_id
        )

async def execute_weather_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """执行天气工具"""
    logger.info(f"[TOOL-EXEC] 开始执行工具")
    logger.info(f"   - 工具名称: {tool_name}")
    logger.info(f"   - 参数: {arguments}")
    
    try:
        if tool_name == "get_current_weather":
            logger.info(f"[TOOL-EXEC] 路由到 get_current_weather")
            result = await get_current_weather(arguments)
        elif tool_name == "get_weather_forecast":
            logger.info(f"[TOOL-EXEC] 路由到 get_weather_forecast")
            result = await get_weather_forecast(arguments)
        elif tool_name == "search_city":
            logger.info(f"[TOOL-EXEC] 路由到 search_city")
            result = await search_city(arguments)
        elif tool_name == "get_air_quality":
            logger.info(f"[TOOL-EXEC] 路由到 get_air_quality")
            result = await get_air_quality(arguments)
        else:
            logger.error(f"[TOOL-EXEC] 未知工具: {tool_name}")
            raise ValueError(f"Unknown tool: {tool_name}")
            
        logger.info(f"[TOOL-EXEC] 工具执行成功")
        logger.info(f"   - 结果类型: {type(result)}")
        logger.info(f"   - 结果长度: {len(str(result))} 字符")
        logger.info(f"   - 结果预览: {str(result)[:200]}...")
        
        return result
        
    except Exception as e:
        logger.error(f"[TOOL-EXEC] 工具执行失败: {e}")
        logger.error(f"   - 错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
        raise

async def get_current_weather(args: Dict[str, Any]) -> str:
    """获取当前天气"""
    city = args.get("city")
    units = args.get("units", "metric")
    api_service = args.get("api_service", DEFAULT_API)
    
    if not city:
        raise ValueError("城市参数不能为空")
    
    if api_service not in WEATHER_APIS:
        raise ValueError(f"不支持的API服务: {api_service}")
    
    config = WEATHER_APIS[api_service]
    
    try:
        async with httpx.AsyncClient() as client:
            if api_service == "openweather":
                url = f"{config['base_url']}/weather"
                params = {
                    "q": city,
                    config['param_name']: config['api_key'],
                    "units": units,
                    "lang": "zh_cn"
                }
            elif api_service == "weatherapi":
                url = f"{config['base_url']}/current.json"
                params = {
                    config['param_name']: config['api_key'],
                    "q": city,
                    "lang": "zh"
                }
            
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code == 401:
                return f"❌ API密钥无效或已过期 ({api_service})"
            elif response.status_code == 404:
                return f"❌ 未找到城市: {city}"
            elif response.status_code != 200:
                return f"❌ API请求失败: {response.status_code} - {response.text}"
            
            data = response.json()
            
            if api_service == "openweather":
                return format_openweather_current(data, units)
            elif api_service == "weatherapi":
                return format_weatherapi_current(data)
    
    except httpx.TimeoutException:
        return f"❌ 请求超时，请检查网络连接"
    except Exception as e:
        return f"❌ 查询失败: {str(e)}"

async def get_weather_forecast(args: Dict[str, Any]) -> str:
    """获取天气预报"""
    city = args.get("city")
    days = args.get("days", 3)
    api_service = args.get("api_service", DEFAULT_API)
    
    if api_service == "openweather":
        # OpenWeatherMap 5天预报
        config = WEATHER_APIS[api_service]
        url = f"{config['base_url']}/forecast"
        params = {
            "q": city,
            config['param_name']: config['api_key'],
            "units": "metric",
            "lang": "zh_cn"
        }
    elif api_service == "weatherapi":
        # WeatherAPI 预报
        config = WEATHER_APIS[api_service]
        url = f"{config['base_url']}/forecast.json"
        params = {
            config['param_name']: config['api_key'],
            "q": city,
            "days": days,
            "lang": "zh"
        }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return f"❌ 预报查询失败: {response.status_code}"
            
            data = response.json()
            
            if api_service == "openweather":
                return format_openweather_forecast(data)
            elif api_service == "weatherapi":
                return format_weatherapi_forecast(data)
    
    except Exception as e:
        return f"❌ 预报查询失败: {str(e)}"

async def search_city(args: Dict[str, Any]) -> str:
    """搜索城市"""
    query = args.get("query")
    limit = args.get("limit", 5)
    
    # 使用OpenWeatherMap的地理编码API
    config = WEATHER_APIS["openweather"]
    url = f"http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": query,
        "limit": limit,
        "appid": config['api_key']
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return f"❌ 城市搜索失败: {response.status_code}"
            
            cities = response.json()
            
            if not cities:
                return f"未找到匹配的城市: {query}"
            
            result = f"🌍 找到 {len(cities)} 个城市:\n\n"
            for i, city in enumerate(cities, 1):
                name = city.get('name', '')
                country = city.get('country', '')
                state = city.get('state', '')
                lat = city.get('lat', 0)
                lon = city.get('lon', 0)
                
                location = f"{name}"
                if state:
                    location += f", {state}"
                location += f", {country}"
                
                result += f"{i}. {location}\n   坐标: ({lat:.2f}, {lon:.2f})\n"
            
            return result
    
    except Exception as e:
        return f"❌ 城市搜索失败: {str(e)}"

async def get_air_quality(args: Dict[str, Any]) -> str:
    """获取空气质量"""
    city = args.get("city")
    api_service = args.get("api_service", DEFAULT_API)
    
    if api_service == "weatherapi":
        config = WEATHER_APIS[api_service]
        url = f"{config['base_url']}/current.json"
        params = {
            config['param_name']: config['api_key'],
            "q": city,
            "aqi": "yes"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    return f"❌ 空气质量查询失败: {response.status_code}"
                
                data = response.json()
                current = data.get('current', {})
                air_quality = current.get('air_quality', {})
                
                if not air_quality:
                    return f"❌ 该地区暂无空气质量数据"
                
                location = data.get('location', {})
                city_name = location.get('name', city)
                country = location.get('country', '')
                
                co = air_quality.get('co', 0)
                no2 = air_quality.get('no2', 0)
                o3 = air_quality.get('o3', 0)
                pm2_5 = air_quality.get('pm2_5', 0)
                pm10 = air_quality.get('pm10', 0)
                us_epa_index = air_quality.get('us-epa-index', 0)
                
                # EPA指数等级
                epa_levels = {
                    1: "优秀 (Good)",
                    2: "中等 (Moderate)", 
                    3: "对敏感人群不健康 (Unhealthy for Sensitive Groups)",
                    4: "不健康 (Unhealthy)",
                    5: "非常不健康 (Very Unhealthy)",
                    6: "有害 (Hazardous)"
                }
                
                level = epa_levels.get(us_epa_index, "未知")
                
                result = f"🌬️ {city_name}, {country} 空气质量报告\n\n"
                result += f"📊 EPA指数: {us_epa_index} ({level})\n\n"
                result += f"具体指标:\n"
                result += f"• CO (一氧化碳): {co:.1f} μg/m³\n"
                result += f"• NO₂ (二氧化氮): {no2:.1f} μg/m³\n"
                result += f"• O₃ (臭氧): {o3:.1f} μg/m³\n"
                result += f"• PM2.5: {pm2_5:.1f} μg/m³\n"
                result += f"• PM10: {pm10:.1f} μg/m³\n"
                
                return result
        
        except Exception as e:
            return f"❌ 空气质量查询失败: {str(e)}"
    
    else:
        return "❌ 当前API服务不支持空气质量查询，请使用 weatherapi"

def format_openweather_current(data: Dict[str, Any], units: str) -> str:
    """格式化OpenWeatherMap当前天气数据"""
    main = data.get('main', {})
    weather = data.get('weather', [{}])[0]
    wind = data.get('wind', {})
    sys = data.get('sys', {})
    
    city = data.get('name', '')
    country = sys.get('country', '')
    
    temp = main.get('temp', 0)
    feels_like = main.get('feels_like', 0)
    humidity = main.get('humidity', 0)
    pressure = main.get('pressure', 0)
    
    description = weather.get('description', '')
    wind_speed = wind.get('speed', 0)
    
    # 温度单位
    temp_unit = "°C" if units == "metric" else "°F" if units == "imperial" else "K"
    speed_unit = "m/s" if units == "metric" else "mph"
    
    result = f"🌤️ {city}, {country} 当前天气\n\n"
    result += f"🌡️ 温度: {temp:.1f}{temp_unit} (体感 {feels_like:.1f}{temp_unit})\n"
    result += f"☁️ 天气: {description}\n"
    result += f"💧 湿度: {humidity}%\n"
    result += f"🌪️ 风速: {wind_speed:.1f} {speed_unit}\n"
    result += f"📊 气压: {pressure} hPa\n"
    
    return result

def format_weatherapi_current(data: Dict[str, Any]) -> str:
    """格式化WeatherAPI当前天气数据"""
    location = data.get('location', {})
    current = data.get('current', {})
    condition = current.get('condition', {})
    
    city = location.get('name', '')
    country = location.get('country', '')
    
    temp_c = current.get('temp_c', 0)
    feelslike_c = current.get('feelslike_c', 0)
    humidity = current.get('humidity', 0)
    pressure_mb = current.get('pressure_mb', 0)
    wind_kph = current.get('wind_kph', 0)
    wind_dir = current.get('wind_dir', '')
    uv = current.get('uv', 0)
    
    condition_text = condition.get('text', '')
    
    result = f"🌤️ {city}, {country} 当前天气\n\n"
    result += f"🌡️ 温度: {temp_c}°C (体感 {feelslike_c}°C)\n"
    result += f"☁️ 天气: {condition_text}\n"
    result += f"💧 湿度: {humidity}%\n"
    result += f"🌪️ 风速: {wind_kph} km/h ({wind_dir})\n"
    result += f"📊 气压: {pressure_mb} mb\n"
    result += f"☀️ UV指数: {uv}\n"
    
    return result

def format_openweather_forecast(data: Dict[str, Any]) -> str:
    """格式化OpenWeatherMap预报数据"""
    city_data = data.get('city', {})
    forecasts = data.get('list', [])
    
    city = city_data.get('name', '')
    country = city_data.get('country', '')
    
    result = f"📅 {city}, {country} 天气预报\n\n"
    
    # 按天分组
    daily_forecasts = {}
    for forecast in forecasts:
        dt_txt = forecast.get('dt_txt', '')
        date = dt_txt.split(' ')[0]
        
        if date not in daily_forecasts:
            daily_forecasts[date] = []
        daily_forecasts[date].append(forecast)
    
    for date, day_forecasts in list(daily_forecasts.items())[:3]:
        # 取当天中午的预报作为代表
        noon_forecast = day_forecasts[len(day_forecasts)//2]
        
        main = noon_forecast.get('main', {})
        weather = noon_forecast.get('weather', [{}])[0]
        
        temp_max = max([f['main']['temp_max'] for f in day_forecasts])
        temp_min = min([f['main']['temp_min'] for f in day_forecasts])
        
        description = weather.get('description', '')
        
        result += f"📆 {date}\n"
        result += f"   🌡️ {temp_min:.1f}°C ~ {temp_max:.1f}°C\n"
        result += f"   ☁️ {description}\n\n"
    
    return result

def format_weatherapi_forecast(data: Dict[str, Any]) -> str:
    """格式化WeatherAPI预报数据"""
    location = data.get('location', {})
    forecast = data.get('forecast', {})
    forecast_days = forecast.get('forecastday', [])
    
    city = location.get('name', '')
    country = location.get('country', '')
    
    result = f"📅 {city}, {country} 天气预报\n\n"
    
    for day_data in forecast_days:
        date = day_data.get('date', '')
        day = day_data.get('day', {})
        condition = day.get('condition', {})
        
        maxtemp_c = day.get('maxtemp_c', 0)
        mintemp_c = day.get('mintemp_c', 0)
        condition_text = condition.get('text', '')
        chance_of_rain = day.get('chance_of_rain', 0)
        
        result += f"📆 {date}\n"
        result += f"   🌡️ {mintemp_c}°C ~ {maxtemp_c}°C\n"
        result += f"   ☁️ {condition_text}\n"
        result += f"   🌧️ 降雨概率: {chance_of_rain}%\n\n"
    
    return result

if __name__ == "__main__":
    print("启动真实天气查询MCP服务器")
    print("服务地址: http://localhost:8084")
    print("可用工具:")
    for tool in WEATHER_TOOLS:
        print(f"   - {tool['name']}: {tool['description']}")
    print("\n请配置真实的API密钥:")
    print("   1. OpenWeatherMap: https://openweathermap.org/api")
    print("   2. WeatherAPI: https://www.weatherapi.com/")
    print("\n修改 WEATHER_APIS 中的 api_key 字段")
    
    uvicorn.run(
        app,
        host="127.0.0.1",  # 改为127.0.0.1
        port=8085,          # 改为8085端口
        log_level="info"
    )