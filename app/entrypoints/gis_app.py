from app.main import create_gis_app

# 暂时禁用 GIS：该入口仍保留文件，但返回的是不注册 GIS 路由、不启动 GIS 引擎的占位 app。
app = create_gis_app()
