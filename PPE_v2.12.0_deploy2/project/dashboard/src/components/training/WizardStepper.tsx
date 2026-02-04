import React from 'react';
import { Check, Upload, Tag, Cpu, Trophy } from 'lucide-react';

export interface WizardStep {
  id: string;
  number: number;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
  count?: number;
  total?: number;
  isComplete: boolean;
  isActive: boolean;
}

interface WizardStepperProps {
  steps: WizardStep[];
  onStepClick: (stepId: string) => void;
  className?: string;
}

export function WizardStepper({ steps, onStepClick, className = '' }: WizardStepperProps) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-4 ${className}`}>
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isLast = index === steps.length - 1;
          
          // Determine step status
          const status = step.isComplete ? 'complete' : step.isActive ? 'active' : 'pending';
          
          // Calculate progress text
          let progressText = '';
          if (step.count !== undefined && step.total !== undefined) {
            progressText = `${step.count}/${step.total}`;
          } else if (step.count !== undefined) {
            progressText = `${step.count}`;
          }
          
          return (
            <React.Fragment key={step.id}>
              {/* Step */}
              <button
                onClick={() => onStepClick(step.id)}
                className={`
                  flex flex-col items-center gap-2 p-3 rounded-lg transition-all min-w-[100px]
                  ${status === 'active' 
                    ? 'bg-primary-50 ring-2 ring-primary-500 ring-offset-2' 
                    : status === 'complete'
                      ? 'bg-success-50 hover:bg-success-100'
                      : 'bg-gray-50 hover:bg-gray-100'
                  }
                `}
                aria-current={step.isActive ? 'step' : undefined}
              >
                {/* Circle with icon/check */}
                <div className={`
                  w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold
                  ${status === 'complete' 
                    ? 'bg-success-500 text-white' 
                    : status === 'active'
                      ? 'bg-primary-500 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }
                `}>
                  {status === 'complete' ? (
                    <Check className="w-5 h-5" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>
                
                {/* Step number and label */}
                <div className="text-center">
                  <p className={`
                    text-xs font-medium
                    ${status === 'active' ? 'text-primary-700' : status === 'complete' ? 'text-success-700' : 'text-gray-500'}
                  `}>
                    Шаг {step.number}
                  </p>
                  <p className={`
                    text-sm font-semibold
                    ${status === 'active' ? 'text-primary-900' : status === 'complete' ? 'text-success-900' : 'text-gray-700'}
                  `}>
                    {step.shortLabel}
                  </p>
                  
                  {/* Progress indicator */}
                  {progressText && (
                    <p className={`
                      text-xs mt-0.5
                      ${status === 'complete' ? 'text-success-600' : 'text-gray-500'}
                    `}>
                      {progressText}
                    </p>
                  )}
                </div>
              </button>
              
              {/* Connector line */}
              {!isLast && (
                <div className="flex-1 mx-2">
                  <div className={`
                    h-1 rounded-full transition-colors
                    ${steps[index + 1]?.isComplete || steps[index + 1]?.isActive
                      ? 'bg-primary-300'
                      : 'bg-gray-200'
                    }
                  `} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// Navigation buttons component
interface WizardNavigationProps {
  currentStep: number;
  totalSteps: number;
  onPrevious: () => void;
  onNext: () => void;
  canGoNext?: boolean;
  nextLabel?: string;
  previousLabel?: string;
  showPrevious?: boolean;
  showNext?: boolean;
}

export function WizardNavigation({
  currentStep,
  totalSteps,
  onPrevious,
  onNext,
  canGoNext = true,
  nextLabel,
  previousLabel = '← Назад',
  showPrevious = true,
  showNext = true,
}: WizardNavigationProps) {
  const stepLabels = ['Данные', 'Разметка', 'Обучение', 'Результаты'];
  const defaultNextLabel = currentStep < totalSteps 
    ? `Далее: ${stepLabels[currentStep]} →` 
    : 'Готово';
  
  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
      {/* Previous button */}
      <div>
        {showPrevious && currentStep > 1 && (
          <button
            onClick={onPrevious}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {previousLabel}
          </button>
        )}
      </div>
      
      {/* Step indicator */}
      <div className="text-sm text-gray-500">
        Шаг {currentStep} из {totalSteps}
      </div>
      
      {/* Next button */}
      <div>
        {showNext && currentStep < totalSteps && (
          <button
            onClick={onNext}
            disabled={!canGoNext}
            className={`
              px-4 py-2 text-sm font-medium rounded-lg transition-colors
              ${canGoNext
                ? 'bg-primary-600 text-white hover:bg-primary-700'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            {nextLabel || defaultNextLabel}
          </button>
        )}
      </div>
    </div>
  );
}

// Default step configuration
export function getDefaultSteps(
  uploadCount: number,
  annotatedCount: number,
  totalImages: number,
  trainedModelsCount: number,
  activeTab: string
): WizardStep[] {
  const MIN_IMAGES = 10;
  const MIN_ANNOTATIONS = 20;
  
  const hasEnoughImages = uploadCount >= MIN_IMAGES;
  const hasEnoughAnnotations = annotatedCount >= MIN_ANNOTATIONS;
  
  return [
    {
      id: 'upload',
      number: 1,
      label: 'Загрузка данных',
      shortLabel: 'Данные',
      icon: Upload,
      count: uploadCount,
      total: MIN_IMAGES,
      isComplete: hasEnoughImages,
      isActive: activeTab === 'upload',
    },
    {
      id: 'annotate',
      number: 2,
      label: 'Разметка объектов',
      shortLabel: 'Разметка',
      icon: Tag,
      count: annotatedCount,
      total: totalImages,
      isComplete: hasEnoughAnnotations,
      isActive: activeTab === 'annotate',
    },
    {
      id: 'train',
      number: 3,
      label: 'Запуск обучения',
      shortLabel: 'Обучение',
      icon: Cpu,
      isComplete: trainedModelsCount > 0,
      isActive: activeTab === 'train',
    },
    {
      id: 'models',
      number: 4,
      label: 'Результаты обучения',
      shortLabel: 'Результаты',
      icon: Trophy,
      count: trainedModelsCount,
      isComplete: trainedModelsCount > 0,
      isActive: activeTab === 'models',
    },
  ];
}
