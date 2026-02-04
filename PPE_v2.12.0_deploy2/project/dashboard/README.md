# 🖥️ PPE Detection Dashboard

Веб-интерфейс для системы контроля средств индивидуальной защиты.

## 📋 Функциональность

### Страницы

| Страница | Описание |
|----------|----------|
| **Dashboard** | Главный экран с камерами и лентой нарушений |
| **Violations** | Журнал всех нарушений с фильтрами и экспортом |
| **Analytics** | Графики и статистика |
| **Settings** | Настройки камер и системы |
| **Login** | Авторизация |

### Возможности

- 🎥 **Live-видео** с камер через WebSocket
- 🔔 **Real-time уведомления** о нарушениях
- 🔊 **Звуковые алерты** при обнаружении
- 📊 **Графики и аналитика** (Recharts)
- 📥 **Экспорт в Excel** 
- 🖥️ **Kiosk Mode** для диспетчерской
- 🔐 **JWT авторизация**
- 📱 **Адаптивный дизайн**

## 🛠️ Технологии

- **React 18** + TypeScript
- **Vite** - сборка
- **Tailwind CSS** - стили
- **Zustand** - state management
- **TanStack Query** - data fetching
- **Recharts** - графики
- **Lucide React** - иконки

## 🚀 Запуск

### Разработка

```bash
cd dashboard

# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev
```

Dashboard будет доступен на http://localhost:3000

### Production сборка

```bash
# Сборка
npm run build

# Превью
npm run preview
```

### Docker

```bash
# Сборка образа
docker build -t ppe-dashboard .

# Запуск
docker run -p 80:80 ppe-dashboard
```

## 🔧 Конфигурация

### API Proxy (vite.config.ts)

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
},
```

### Environment Variables

Создайте `.env.local` для переопределения:

```env
VITE_API_URL=http://api.example.com
VITE_WS_URL=ws://api.example.com
```

## 📁 Структура

```
dashboard/
├── src/
│   ├── api/           # API клиент
│   ├── components/    # React компоненты
│   │   ├── camera/    # Камеры
│   │   ├── layout/    # Layout
│   │   ├── stats/     # Статистика
│   │   └── violations/# Нарушения
│   ├── hooks/         # Custom hooks
│   │   ├── useWebSocket.ts
│   │   └── useSound.ts
│   ├── pages/         # Страницы
│   ├── store/         # Zustand stores
│   ├── types/         # TypeScript типы
│   ├── App.tsx        # Роутинг
│   └── main.tsx       # Entry point
├── public/
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## 🎨 Дизайн-система

### Цвета

| Цвет | HEX | Использование |
|------|-----|---------------|
| Primary | `#3B82F6` | Кнопки, ссылки |
| Danger | `#EF4444` | Нарушения, ошибки |
| Warning | `#F97316` | Предупреждения |
| Success | `#22C55E` | Успех, норма |

### Компоненты

```tsx
// Кнопки
<button className="btn-primary">Primary</button>
<button className="btn-outline">Outline</button>
<button className="btn-ghost">Ghost</button>

// Карточки
<div className="card p-4">Content</div>

// Бейджи
<span className="badge-danger">Новое</span>
<span className="badge-success">OK</span>

// Инпуты
<input className="input" />
<select className="input">...</select>
```

## 🔐 Авторизация

Dashboard использует JWT токены:

```typescript
// Login
const response = await api.login({ username, password });
// → { access_token, token_type, expires_in }

// Использование
headers: {
  Authorization: `Bearer ${token}`
}

// WebSocket
new WebSocket(`ws://host/ws?token=${token}`)
```

## 📡 WebSocket

Формат сообщений:

```typescript
// Входящие
{ type: 'violation', data: Violation }
{ type: 'camera_status', data: { camera_id, status } }
{ type: 'pong' }

// Исходящие
{ type: 'ping' }
```

## 🧪 Тестирование

```bash
# Линтинг
npm run lint

# (будущее) Тесты
npm test
```

## 📝 TODO

- [ ] Unit тесты (Vitest)
- [ ] E2E тесты (Playwright)
- [ ] Storybook для компонентов
- [ ] PWA поддержка
- [ ] Темная тема

---

**Версия:** 2.1.0  
**Обновлено:** Ноябрь 2024
