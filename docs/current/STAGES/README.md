# Stage Design

Each stage has a single responsibility in the pipeline and persists its output for later stages.

## Stage map

| Stage | Main responsibility | Main contract |
| --- | --- | --- |
| [Init](init.md) | Discover SQL units and collect metadata | [Init contracts](../CONTRACTS/init.md) |
| [Parse](parse.md) | Expand dynamic SQL into branches | [Parse contracts](../CONTRACTS/parse.md) |
| [Recognition](recognition.md) | Build plans and baselines | [Recognition contracts](../CONTRACTS/recognition.md) |
| [Optimize](optimize.md) | Generate and validate optimized SQL | [Optimize contracts](../CONTRACTS/optimize.md) |
| [Result](result.md) | Rank findings and emit the final report | [Result contracts](../CONTRACTS/result.md) |

## Reading order

1. [Init](init.md)
2. [Parse](parse.md)
3. [Recognition](recognition.md)
4. [Optimize](optimize.md)
5. [Result](result.md)
