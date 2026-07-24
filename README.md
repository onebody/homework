# Homework Projects

暑假作业相关项目合集。

---

## 📦 points-system

**打卡积分兑换奖品系统**

一个独立的「打卡赚积分 → 积分兑换奖品 → 抽奖」功能模块。

- **技术栈**：FastAPI + SQLAlchemy 2.0 + SQLite + 原生 HTML/JS
- **特点**：无构建依赖，可独立运行，易于移植
- **功能**：
  - 每日打卡赚积分
  - 积分兑换抽奖券
  - 加权随机抽奖
  - 完整积分流水对账
  - 奖品管理与库存控制

**快速启动**：
```bash
cd points-system/backend
python seed.py
python run.py
```

访问 http://127.0.0.1:8000

---

## 📅 summer-homework-checkin

**暑假作业打卡登记系统（三年级）**

面向小学生的暑假日常作业学习打卡全周期管理系统。

- **技术栈**：FastAPI + SQLAlchemy 2.0 + Vue3 CDN + SQLite
- **架构**：前后端分离，学生端 H5 适配手机/平板，独立管理后台
- **核心功能**：
  - 每日打卡（限 1 次）+ 照片上传
  - 连续打卡统计 + 补卡功能（每月≤3次）
  - 防代打卡：照片真实性 + 地理位置 + 人脸比对
  - 7 天解锁抽奖资格
  - 奖品管理 + 积分兑换
  - 家长绑定 + 实时通知
  - 暑假全周期可视化报告
  - **闯关任务打卡**（新增）：管理员设定任务、学生打卡、审核通过自动发积分

**快速启动**：
```bash
cd summer-homework-checkin/backend
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload
```

- 学生端：http://localhost:8000/
- 管理端：http://localhost:8000/admin/
- 默认账号：admin / admin123

---

## 📄 License

MIT
