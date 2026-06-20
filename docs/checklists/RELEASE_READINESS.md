# 发布前清单

- [ ] 后端测试通过
- [ ] 前端 `typecheck / lint / build` 通过
- [ ] 关键流程人工走查完成
- [ ] 高风险变更已覆盖回归用例
- [ ] PostgreSQL-only 运行态执行 `scripts/postgres_operational_readiness.sh` 通过；涉及数据库发布时已用 `POSTGRES_OPS_BACKUP_RESTORE=run` 完成新备份和恢复演练
- [ ] 文档入口可指向当前有效规范
- [ ] 已确认未提交敏感配置或用户数据
- [ ] 已确认变更日志或审计记录已更新
