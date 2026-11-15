# 前端模块（Vue 3 + Vite）

「科研助手 Agent 系统」的前端界面。入口 `src/App.vue`，其余源码在 `src/`，静态资源在 `public/`。

## 运行

```powershell
npm install
npm run dev      # http://localhost:5173
```

`vite.config.js` 已配置 `/api` → `http://127.0.0.1:8000` 的同源代理，**后端需先启动**，否则页面会拿不到数据。

## 构建

```powershell
npm run build    # 产物输出到 dist/
```

## 完整文档

安装运行、环境变量、评审模式、演示部署等说明，见仓库根目录 [README](../README.md)。
