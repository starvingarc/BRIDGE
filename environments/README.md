# Conda Environment Contracts

| EnvironmentSpec | Conda name | State | Used by |
|---|---|---|---|
| `ENV-P0-CORE-v0.1` | `bridge-p0-core` | rebuild validation required | Tool Runtime, P0-01 and future Python scientific executors |
| `ENV-EVIDENCE-v0.1` | `bridge-p0-evidence` | proposed | P0-08 to P0-11 deterministic evidence and release services |

The YAML files describe required runtime capabilities. Scientific method-specific R, JAX, GPU, mixed-species and competitor environments remain conditional and must receive separate versioned specifications before their executors can be implemented.

No environment installation implies scientific validation or method promotion.
