# 来源字段

auction_result 与 resale_notice 的 lot 标识批次，transaction_id 标识单笔交易，effective_on 决定交易先后。resale_notice 还记录 buyer_type，使育肥留存与屠宰去向可区分。transaction_retraction 通过 transaction_id 指向原交易；heads 表示被撤销或更正的头数。字段相等不证明两份原文已经完整或同版。

来源目录中的 expected_revision 表示该链接当前要求核实的来源版次；normal.json 为 v1，revised.json 将第一份来源改指同链接 v2。旧版原文仍可用于历史视图。
