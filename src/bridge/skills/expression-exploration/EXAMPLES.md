# Expression exploration examples

| Request and supplied state | Expected behavior |
|---|---|
| “只做输入质控”；raw counts confirmed, no QC yet | Load expression-exploration, prepare_qc with the supplied upload/matrix; wait for plan approval. |
| “解释这个表达谱图，先别重跑”；current observations shared | Load expression-exploration, reply with relevant observation aliases; no new plan. |
| “这些细胞当成重复做条件差异”；no biological replicates | Explain the replication gap; preserve descriptive_only/not_estimable. |
| “刚才说错了，这个不是原始计数” | review_inputs; chat does not replace the committed declaration. |
| “你好” | Ordinary reply; loading a Skill is unnecessary. |

These are behavioral cases, not measurements or authorized execution requests.
