/**
 * Model Selector Component
 * ========================
 * 
 * Выбор модели YOLO для обучения.
 * Поддерживает YOLOv8, YOLOv9, YOLOv10, YOLOv11.
 */

import { Cpu, Zap, Target, Info, CheckCircle } from 'lucide-react';

// Model configurations
export const YOLO_MODELS = {
  yolov8: {
    name: 'YOLOv8',
    description: 'Стабильная и проверенная модель. Лучший выбор для начала.',
    badge: 'Рекомендуется',
    badgeColor: 'bg-green-100 text-green-700',
    sizes: [
      { id: 'n', name: 'Nano', params: '3.2M', speed: 'Очень быстрая', accuracy: 'Базовая', gpu_mem: '~2 GB' },
      { id: 's', name: 'Small', params: '11.2M', speed: 'Быстрая', accuracy: 'Хорошая', gpu_mem: '~4 GB' },
      { id: 'm', name: 'Medium', params: '25.9M', speed: 'Средняя', accuracy: 'Высокая', gpu_mem: '~6 GB' },
      { id: 'l', name: 'Large', params: '43.7M', speed: 'Медленная', accuracy: 'Очень высокая', gpu_mem: '~8 GB' },
      { id: 'x', name: 'XLarge', params: '68.2M', speed: 'Очень медленная', accuracy: 'Максимальная', gpu_mem: '~12 GB' },
    ]
  },
  yolov9: {
    name: 'YOLOv9',
    description: 'Улучшенная архитектура GELAN. Лучше обобщение на новых данных.',
    badge: 'Продвинутая',
    badgeColor: 'bg-blue-100 text-blue-700',
    sizes: [
      { id: 't', name: 'Tiny', params: '2.0M', speed: 'Очень быстрая', accuracy: 'Базовая', gpu_mem: '~2 GB' },
      { id: 's', name: 'Small', params: '7.2M', speed: 'Быстрая', accuracy: 'Хорошая', gpu_mem: '~3 GB' },
      { id: 'm', name: 'Medium', params: '20.1M', speed: 'Средняя', accuracy: 'Высокая', gpu_mem: '~5 GB' },
      { id: 'c', name: 'Compact', params: '25.5M', speed: 'Средняя', accuracy: 'Высокая', gpu_mem: '~6 GB' },
      { id: 'e', name: 'Extended', params: '58.1M', speed: 'Медленная', accuracy: 'Максимальная', gpu_mem: '~10 GB' },
    ]
  },
  yolov10: {
    name: 'YOLOv10',
    description: 'Без NMS постобработки. Быстрее inference, идеально для real-time.',
    badge: 'Real-time',
    badgeColor: 'bg-purple-100 text-purple-700',
    sizes: [
      { id: 'n', name: 'Nano', params: '2.3M', speed: 'Ультра быстрая', accuracy: 'Базовая', gpu_mem: '~1.5 GB' },
      { id: 's', name: 'Small', params: '7.2M', speed: 'Очень быстрая', accuracy: 'Хорошая', gpu_mem: '~3 GB' },
      { id: 'm', name: 'Medium', params: '15.4M', speed: 'Быстрая', accuracy: 'Высокая', gpu_mem: '~4 GB' },
      { id: 'b', name: 'Balanced', params: '19.1M', speed: 'Средняя', accuracy: 'Высокая', gpu_mem: '~5 GB' },
      { id: 'l', name: 'Large', params: '24.4M', speed: 'Средняя', accuracy: 'Очень высокая', gpu_mem: '~6 GB' },
      { id: 'x', name: 'XLarge', params: '29.5M', speed: 'Медленная', accuracy: 'Максимальная', gpu_mem: '~8 GB' },
    ]
  },
  yolov11: {
    name: 'YOLOv11',
    description: 'Новейшая модель Ultralytics. Лучший баланс скорости и точности.',
    badge: 'Новинка 2024',
    badgeColor: 'bg-orange-100 text-orange-700',
    sizes: [
      { id: 'n', name: 'Nano', params: '2.6M', speed: 'Очень быстрая', accuracy: 'Хорошая', gpu_mem: '~2 GB' },
      { id: 's', name: 'Small', params: '9.4M', speed: 'Быстрая', accuracy: 'Высокая', gpu_mem: '~3 GB' },
      { id: 'm', name: 'Medium', params: '20.1M', speed: 'Средняя', accuracy: 'Очень высокая', gpu_mem: '~5 GB' },
      { id: 'l', name: 'Large', params: '25.3M', speed: 'Средняя', accuracy: 'Очень высокая', gpu_mem: '~6 GB' },
      { id: 'x', name: 'XLarge', params: '56.9M', speed: 'Медленная', accuracy: 'Максимальная', gpu_mem: '~10 GB' },
    ]
  }
};

export type ModelType = keyof typeof YOLO_MODELS;
export type ModelSize = string;

interface ModelSelectorProps {
  selectedModel: ModelType;
  selectedSize: ModelSize;
  onModelChange: (model: ModelType) => void;
  onSizeChange: (size: ModelSize) => void;
}

export function ModelSelector({
  selectedModel,
  selectedSize,
  onModelChange,
  onSizeChange
}: ModelSelectorProps) {
  const currentModelConfig = YOLO_MODELS[selectedModel];
  const currentSize = currentModelConfig.sizes.find(s => s.id === selectedSize) || currentModelConfig.sizes[0];

  return (
    <div className="space-y-4">
      {/* Model Type Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Архитектура модели
        </label>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {(Object.entries(YOLO_MODELS) as [ModelType, typeof YOLO_MODELS.yolov8][]).map(([key, model]) => (
            <button
              key={key}
              onClick={() => {
                onModelChange(key);
                // Reset size to first available
                onSizeChange(model.sizes[0].id);
              }}
              className={`
                relative p-4 rounded-lg border-2 text-left transition-all
                ${selectedModel === key 
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200' 
                  : 'border-gray-200 hover:border-gray-300 bg-white'}
              `}
            >
              {selectedModel === key && (
                <CheckCircle className="absolute top-2 right-2 w-5 h-5 text-primary-600" />
              )}
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-gray-900">{model.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${model.badgeColor}`}>
                  {model.badge}
                </span>
              </div>
              <p className="text-xs text-gray-500 line-clamp-2">{model.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Model Size Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Размер модели ({currentModelConfig.name})
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {currentModelConfig.sizes.map((size) => (
            <button
              key={size.id}
              onClick={() => onSizeChange(size.id)}
              className={`
                p-3 rounded-lg border-2 text-left transition-all
                ${selectedSize === size.id 
                  ? 'border-primary-500 bg-primary-50' 
                  : 'border-gray-200 hover:border-gray-300 bg-white'}
              `}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-900">{size.name}</span>
                <span className="text-xs text-gray-500">{size.params} params</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-1 text-gray-600">
                  <Zap className="w-3 h-3" />
                  <span>{size.speed}</span>
                </div>
                <div className="flex items-center gap-1 text-gray-600">
                  <Target className="w-3 h-3" />
                  <span>{size.accuracy}</span>
                </div>
                <div className="flex items-center gap-1 text-gray-600 col-span-2">
                  <Cpu className="w-3 h-3" />
                  <span>GPU: {size.gpu_mem}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Selected Model Summary */}
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <p className="font-medium text-gray-900">
              Выбрано: {currentModelConfig.name} {currentSize.name}
            </p>
            <p className="text-sm text-gray-600 mt-1">
              {currentSize.params} параметров • {currentSize.speed} • {currentSize.accuracy} точность • {currentSize.gpu_mem} VRAM
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Модель будет автоматически загружена при старте обучения.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Split Selector Component
interface SplitSelectorProps {
  trainSplit: number;
  valSplit: number;
  testSplit: number;
  onTrainChange: (value: number) => void;
  onValChange: (value: number) => void;
  onTestChange: (value: number) => void;
}

export function SplitSelector({
  trainSplit,
  valSplit,
  testSplit,
  onTrainChange,
  onValChange,
  onTestChange
}: SplitSelectorProps) {
  const total = trainSplit + valSplit + testSplit;
  const isValid = Math.abs(total - 1.0) < 0.01;

  const presets = [
    { name: '70/20/10', train: 0.7, val: 0.2, test: 0.1 },
    { name: '80/15/5', train: 0.8, val: 0.15, test: 0.05 },
    { name: '80/20/0', train: 0.8, val: 0.2, test: 0 },
    { name: '90/10/0', train: 0.9, val: 0.1, test: 0 },
  ];

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-700">
        Разделение датасета (Train / Val / Test)
      </label>
      
      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset.name}
            onClick={() => {
              onTrainChange(preset.train);
              onValChange(preset.val);
              onTestChange(preset.test);
            }}
            className={`
              px-3 py-1.5 rounded-lg text-sm border transition-all
              ${trainSplit === preset.train && valSplit === preset.val && testSplit === preset.test
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-gray-200 hover:border-gray-300 text-gray-600'}
            `}
          >
            {preset.name}
          </button>
        ))}
      </div>

      {/* Visual bar */}
      <div className="h-8 rounded-lg overflow-hidden flex">
        <div 
          className="bg-green-500 flex items-center justify-center text-white text-xs font-medium"
          style={{ width: `${trainSplit * 100}%` }}
        >
          Train {(trainSplit * 100).toFixed(0)}%
        </div>
        <div 
          className="bg-blue-500 flex items-center justify-center text-white text-xs font-medium"
          style={{ width: `${valSplit * 100}%` }}
        >
          Val {(valSplit * 100).toFixed(0)}%
        </div>
        {testSplit > 0 && (
          <div 
            className="bg-orange-500 flex items-center justify-center text-white text-xs font-medium"
            style={{ width: `${testSplit * 100}%` }}
          >
            Test {(testSplit * 100).toFixed(0)}%
          </div>
        )}
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="text-xs text-gray-500">Training</label>
          <input
            type="range"
            min="50"
            max="90"
            value={trainSplit * 100}
            onChange={(e) => {
              const newTrain = parseInt(e.target.value) / 100;
              const remaining = 1 - newTrain;
              const valRatio = valSplit / (valSplit + testSplit) || 0.67;
              onTrainChange(newTrain);
              onValChange(remaining * valRatio);
              onTestChange(remaining * (1 - valRatio));
            }}
            className="w-full"
          />
          <span className="text-sm font-medium">{(trainSplit * 100).toFixed(0)}%</span>
        </div>
        <div>
          <label className="text-xs text-gray-500">Validation</label>
          <input
            type="range"
            min="5"
            max="40"
            value={valSplit * 100}
            onChange={(e) => {
              const newVal = parseInt(e.target.value) / 100;
              const remaining = 1 - trainSplit - newVal;
              onValChange(newVal);
              onTestChange(Math.max(0, remaining));
            }}
            className="w-full"
          />
          <span className="text-sm font-medium">{(valSplit * 100).toFixed(0)}%</span>
        </div>
        <div>
          <label className="text-xs text-gray-500">Test</label>
          <input
            type="range"
            min="0"
            max="20"
            value={testSplit * 100}
            onChange={(e) => {
              const newTest = parseInt(e.target.value) / 100;
              onTestChange(newTest);
            }}
            className="w-full"
          />
          <span className="text-sm font-medium">{(testSplit * 100).toFixed(0)}%</span>
        </div>
      </div>

      {!isValid && (
        <p className="text-sm text-red-600">
          Сумма должна быть 100% (сейчас {(total * 100).toFixed(0)}%)
        </p>
      )}
    </div>
  );
}

// Advanced Options Component
interface AdvancedOptionsProps {
  optimizer: string;
  patience: number;
  onOptimizerChange: (value: string) => void;
  onPatienceChange: (value: number) => void;
}

export function AdvancedOptions({
  optimizer,
  patience,
  onOptimizerChange,
  onPatienceChange
}: AdvancedOptionsProps) {
  const optimizers = [
    { id: 'auto', name: 'Auto', description: 'Автоматический выбор' },
    { id: 'SGD', name: 'SGD', description: 'Классический, стабильный' },
    { id: 'Adam', name: 'Adam', description: 'Быстрая сходимость' },
    { id: 'AdamW', name: 'AdamW', description: 'Adam с weight decay' },
  ];

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Оптимизатор
        </label>
        <div className="grid grid-cols-4 gap-2">
          {optimizers.map((opt) => (
            <button
              key={opt.id}
              onClick={() => onOptimizerChange(opt.id)}
              className={`
                p-2 rounded-lg border text-center transition-all
                ${optimizer === opt.id 
                  ? 'border-primary-500 bg-primary-50' 
                  : 'border-gray-200 hover:border-gray-300'}
              `}
            >
              <span className="font-medium text-sm">{opt.name}</span>
              <p className="text-xs text-gray-500">{opt.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Early Stopping Patience: {patience === 0 ? 'Отключено' : `${patience} эпох`}
        </label>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={patience}
          onChange={(e) => onPatienceChange(parseInt(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">
          Остановить обучение если метрика не улучшается N эпох подряд. 0 = отключено.
        </p>
      </div>
    </div>
  );
}

export default ModelSelector;
