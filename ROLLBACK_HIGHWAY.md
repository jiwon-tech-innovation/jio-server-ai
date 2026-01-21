# Highway AI Rollback Reference
## Current Deployment (Before Highway AI)
- **Image**: `541673202749.dkr.ecr.ap-northeast-2.amazonaws.com/jiaa-server-ai:latest`
- **Recorded At**: 2026-01-19T03:50

## Rollback Command
```bash
kubectl set image deployment/jiaa-server-ai jiaa-server-ai=541673202749.dkr.ecr.ap-northeast-2.amazonaws.com/jiaa-server-ai:latest -n jiaa
```

## Highway AI Deployment
- **New Tag**: `highway-v1`
- **Branch**: `demo/highway-ai`
