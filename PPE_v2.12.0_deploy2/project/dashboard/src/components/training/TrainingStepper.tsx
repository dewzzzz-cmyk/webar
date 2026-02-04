import React from 'react';
import { Check } from 'lucide-react';

export interface Step {
  id: string;
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  count?: number;
  total?: number;
  isComplete: boolean;
  isActive: boolean;
}

interface TrainingStepperProps {
  steps: Step[];
  onStepClick: (stepId: string) => void;
}

export function TrainingStepper({ steps, onStepClick }: TrainingStepperProps) {
  return (
    <div className="mb-8">
      {/* Desktop Stepper */}
      <div className="hidden md:block">
        <div className="relative">
          {/* Progress Line */}
          <div className="absolute top-6 left-0 right-0 h-0.5 bg-gray-200">
            <div 
              className="h-full bg-primary-500 transition-all duration-500"
              style={{ 
                width: `${(steps.filter(s => s.isComplete).length / (steps.length - 1)) * 100}%` 
              }}
            />
          </div>
          
          {/* Steps */}
          <div className="relative flex justify-between">
            {steps.map((step, index) => {
              const StepIcon = step.icon;
              const isClickable = step.isComplete || step.isActive || (index > 0 && steps[index - 1].isComplete);
              
              return (
                <button
                  key={step.id}
                  onClick={() => isClickable && onStepClick(step.id)}
                  disabled={!isClickable}
                  className={`flex flex-col items-center group ${isClickable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                >
                  {/* Circle */}
                  <div
                    className={`
                      relative z-10 w-12 h-12 rounded-full flex items-center justify-center
                      border-2 transition-all duration-300
                      ${step.isComplete 
                        ? 'bg-primary-500 border-primary-500 text-white' 
                        : step.isActive
                          ? 'bg-white border-primary-500 text-primary-600 shadow-lg shadow-primary-100'
                          : 'bg-white border-gray-300 text-gray-400'
                      }
                      ${isClickable && !step.isActive ? 'group-hover:border-primary-400 group-hover:shadow-md' : ''}
                    `}
                  >
                    {step.isComplete ? (
                      <Check className="w-6 h-6" />
                    ) : (
                      <StepIcon className="w-5 h-5" />
                    )}
                  </div>
                  
                  {/* Step Number & Label */}
                  <div className="mt-3 text-center">
                    <p className={`text-xs font-bold ${
                      step.isActive ? 'text-primary-600' : step.isComplete ? 'text-primary-500' : 'text-gray-400'
                    }`}>
                      Шаг {index + 1}
                    </p>
                    <p className={`text-sm font-medium mt-0.5 ${
                      step.isActive ? 'text-gray-900' : step.isComplete ? 'text-gray-700' : 'text-gray-500'
                    }`}>
                      {step.label}
                    </p>
                    
                    {/* Count Badge */}
                    {step.count !== undefined && (
                      <p className={`text-xs mt-1 ${
                        step.isActive ? 'text-primary-600' : 'text-gray-400'
                      }`}>
                        {step.total !== undefined 
                          ? `${step.count} / ${step.total}`
                          : step.count
                        }
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Mobile Stepper */}
      <div className="md:hidden">
        <div className="flex items-center justify-between bg-gray-50 rounded-xl p-2">
          {steps.map((step, index) => {
            const isClickable = step.isComplete || step.isActive || (index > 0 && steps[index - 1].isComplete);
            
            return (
              <button
                key={step.id}
                onClick={() => isClickable && onStepClick(step.id)}
                disabled={!isClickable}
                className={`
                  flex-1 flex flex-col items-center py-2 px-1 rounded-lg transition-all
                  ${step.isActive 
                    ? 'bg-white shadow-sm' 
                    : isClickable 
                      ? 'hover:bg-white/50' 
                      : 'opacity-50'
                  }
                `}
              >
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
                  ${step.isComplete 
                    ? 'bg-primary-500 text-white' 
                    : step.isActive
                      ? 'bg-primary-100 text-primary-600'
                      : 'bg-gray-200 text-gray-500'
                  }
                `}>
                  {step.isComplete ? <Check className="w-4 h-4" /> : index + 1}
                </div>
                <span className={`text-xs mt-1 ${step.isActive ? 'font-medium text-gray-900' : 'text-gray-500'}`}>
                  {step.shortLabel}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

interface NavigationButtonsProps {
  onPrev?: () => void;
  onNext?: () => void;
  prevLabel?: string;
  nextLabel?: string;
  prevDisabled?: boolean;
  nextDisabled?: boolean;
  showPrev?: boolean;
  showNext?: boolean;
  nextVariant?: 'primary' | 'success';
}

export function StepNavigation({
  onPrev,
  onNext,
  prevLabel = 'Назад',
  nextLabel = 'Далее',
  prevDisabled = false,
  nextDisabled = false,
  showPrev = true,
  showNext = true,
  nextVariant = 'primary',
}: NavigationButtonsProps) {
  return (
    <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-200">
      <div>
        {showPrev && onPrev && (
          <button
            onClick={onPrev}
            disabled={prevDisabled}
            className="btn-outline flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {prevLabel}
          </button>
        )}
      </div>
      
      <div>
        {showNext && onNext && (
          <button
            onClick={onNext}
            disabled={nextDisabled}
            className={`flex items-center gap-2 ${
              nextVariant === 'success' 
                ? 'btn-primary bg-green-600 hover:bg-green-700' 
                : 'btn-primary'
            }`}
          >
            {nextLabel}
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
