# 二次育肥公开交易与存栏证据接续

现有项目保存育肥成交与转售公告的冻结来源响应。transport 核对请求和原文字节，ledger 保留来源版本，trades 按成交时间列出批次交易并给出每个交易身份的最新版次与有效头数，inventory 计算竞价取得与转售后留存的头数。collection 记录来源目录和接收进度，view 展示交易、存栏及待核范围，archive 保留已发布视图。成交更正按来源版次替换当前数量，交易撤回按 transaction_id 扣减对应成交的有效头数；撤回不作为新交易，未核对的版本或交易引用显示为待核而不按零头数处理。合成样例不访问外部站点。来源字段见 docs/source-contract.md。

在项目根目录运行：

    python -m unittest discover -s tests -v
    python -m compileall -q capture_service tests
    python -m capture_service.cli inspect data/normal.json

容器运行：docker build -t pork-collection-008 .；docker run --rm pork-collection-008。
