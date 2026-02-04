# 🚀 PPE Detection System - Kubernetes Deployment

## Структура

```
k8s/
├── base/                    # Базовые манифесты
│   ├── namespace.yaml       # Namespace
│   ├── configmap.yaml       # ConfigMap и Secrets
│   ├── postgres.yaml        # PostgreSQL StatefulSet
│   ├── redis.yaml           # Redis Deployment
│   ├── api.yaml             # API Deployment + HPA
│   ├── detector.yaml        # Detector с GPU
│   ├── capture.yaml         # Capture Service
│   ├── dashboard.yaml       # Dashboard
│   ├── ingress.yaml         # Ingress + TLS
│   └── kustomization.yaml
│
└── overlays/
    ├── staging/             # Staging конфигурация
    │   └── kustomization.yaml
    └── production/          # Production конфигурация
        └── kustomization.yaml
```

## Требования

- Kubernetes 1.25+
- kubectl
- kustomize (или kubectl с поддержкой kustomize)
- NVIDIA GPU Operator (для детектора)
- Ingress Controller (nginx-ingress)
- cert-manager (для TLS)

## Quick Start

### 1. Подготовка кластера

```bash
# Установка NVIDIA GPU Operator
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm install gpu-operator nvidia/gpu-operator

# Установка nginx-ingress
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Установка cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

### 2. Настройка секретов

```bash
# Создайте файл с секретами (НЕ коммитьте в git!)
cat > k8s/overlays/production/secrets.env << EOF
POSTGRES_PASSWORD=your_secure_password
JWT_SECRET=your_64_char_secret_here
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

### 3. Сборка и push Docker образов

```bash
# Сборка образов
docker build -t your-registry.com/ppe/api:v2.2.0 ./services/api
docker build -t your-registry.com/ppe/detector:v2.2.0 ./services/detector
docker build -t your-registry.com/ppe/capture:v2.2.0 ./services/capture
docker build -t your-registry.com/ppe/dashboard:v2.2.0 ./dashboard

# Push в registry
docker push your-registry.com/ppe/api:v2.2.0
docker push your-registry.com/ppe/detector:v2.2.0
docker push your-registry.com/ppe/capture:v2.2.0
docker push your-registry.com/ppe/dashboard:v2.2.0
```

### 4. Деплой

```bash
# Staging
kubectl apply -k k8s/overlays/staging

# Production
kubectl apply -k k8s/overlays/production
```

### 5. Проверка

```bash
# Статус подов
kubectl get pods -n ppe-detection

# Логи API
kubectl logs -f deployment/api -n ppe-detection

# Логи детектора
kubectl logs -f deployment/detector -n ppe-detection
```

## Конфигурация

### Изменение домена

Отредактируйте `k8s/base/ingress.yaml`:
```yaml
spec:
  rules:
    - host: your-domain.com  # <-- Ваш домен
```

### Изменение ресурсов

В overlay файлах можно настроить:
- Количество реплик
- Лимиты CPU/RAM
- Размер GPU памяти

### Масштабирование

API автоматически масштабируется через HPA:
```bash
# Проверка HPA
kubectl get hpa -n ppe-detection

# Ручное масштабирование
kubectl scale deployment/api --replicas=5 -n ppe-detection
```

## Мониторинг

### Prometheus метрики

Все сервисы экспортируют метрики:
- API: `:8000/metrics`
- Detector: `:9100/metrics`
- Capture: `:9100/metrics`

### Установка Prometheus Stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

## Troubleshooting

### Под не запускается

```bash
# Описание пода
kubectl describe pod <pod-name> -n ppe-detection

# События
kubectl get events -n ppe-detection --sort-by='.lastTimestamp'
```

### Проблемы с GPU

```bash
# Проверка GPU нод
kubectl get nodes -l nvidia.com/gpu.present=true

# Проверка GPU в поде
kubectl exec -it deployment/detector -n ppe-detection -- nvidia-smi
```

### Проблемы с Ingress

```bash
# Проверка Ingress
kubectl describe ingress ppe-ingress -n ppe-detection

# Логи ingress controller
kubectl logs -f deployment/ingress-nginx-controller -n ingress-nginx
```

## Безопасность

⚠️ **ВАЖНО для Production:**

1. Используйте **external-secrets** или **sealed-secrets** вместо plain secrets
2. Включите **NetworkPolicies** для изоляции подов
3. Настройте **PodSecurityPolicy** / **Pod Security Standards**
4. Используйте **RBAC** для ограничения доступа
5. Регулярно обновляйте образы (security patches)

### Пример NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: ppe-detection
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: dashboard
        - podSelector:
            matchLabels:
              app: ingress-nginx
      ports:
        - port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
        - podSelector:
            matchLabels:
              app: redis
```

## Backup

### PostgreSQL backup

```bash
# Создание backup
kubectl exec -it statefulset/postgres -n ppe-detection -- \
  pg_dump -U ppe ppe_detection > backup.sql

# Восстановление
kubectl exec -i statefulset/postgres -n ppe-detection -- \
  psql -U ppe ppe_detection < backup.sql
```

---

**Версия:** 2.2  
**Дата:** 2024
