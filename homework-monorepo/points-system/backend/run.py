import uvicorn

if __name__ == "__main__":
    # 通过 import string 启动，确保 app 包可被正确加载
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
