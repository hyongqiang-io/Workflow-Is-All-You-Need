import { useMemo, useCallback, useRef, useState } from 'react';

/**
 * 简单的防抖函数实现
 */
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * 简单的节流函数实现
 */
function throttle<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let lastTime = 0;
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastTime >= wait) {
      lastTime = now;
      func(...args);
    }
  };
}

/**
 * 子工作流展开功能的性能优化配置
 */

// 性能配置常量
export const PERFORMANCE_CONFIG = {
  // 布局计算节流时间（毫秒）
  LAYOUT_THROTTLE_MS: 100,
  
  // API请求防抖时间（毫秒）
  API_DEBOUNCE_MS: 300,
  
  // 最大同时展开的子工作流数量
  MAX_EXPANDED_SUBWORKFLOWS: 3,
  
  // 子工作流节点虚拟化阈值
  VIRTUALIZATION_THRESHOLD: 50,
  
  // 缓存过期时间（毫秒）
  CACHE_EXPIRY_MS: 5 * 60 * 1000, // 5分钟
  
  // 动画性能级别
  ANIMATION_PERFORMANCE: {
    HIGH: 'high',
    MEDIUM: 'medium', 
    LOW: 'low',
    DISABLED: 'disabled'
  }
};

/**
 * 性能监控工具
 */
export class PerformanceMonitor {
  private static instance: PerformanceMonitor;
  private metrics: Map<string, number[]> = new Map();
  private observers: PerformanceObserver[] = [];

  static getInstance(): PerformanceMonitor {
    if (!PerformanceMonitor.instance) {
      PerformanceMonitor.instance = new PerformanceMonitor();
    }
    return PerformanceMonitor.instance;
  }

  // 记录性能指标
  recordMetric(name: string, value: number): void {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }
    
    const values = this.metrics.get(name)!;
    values.push(value);
    
    // 保持最近100个记录
    if (values.length > 100) {
      values.shift();
    }
  }

  // 获取性能统计
  getMetricStats(name: string) {
    const values = this.metrics.get(name) || [];
    if (values.length === 0) return null;

    const sorted = [...values].sort((a, b) => a - b);
    return {
      count: values.length,
      min: sorted[0],
      max: sorted[sorted.length - 1],
      avg: values.reduce((sum, val) => sum + val, 0) / values.length,
      median: sorted[Math.floor(sorted.length / 2)],
      p95: sorted[Math.floor(sorted.length * 0.95)]
    };
  }

  // 开始性能测量
  startMeasure(name: string): () => void {
    const startTime = performance.now();
    
    return () => {
      const endTime = performance.now();
      const duration = endTime - startTime;
      this.recordMetric(name, duration);
      
      // 在开发环境中记录慢操作
      if (process.env.NODE_ENV === 'development' && duration > 100) {
        console.warn(`Slow operation detected: ${name} took ${duration.toFixed(2)}ms`);
      }
    };
  }

  // 清理资源
  cleanup(): void {
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
    this.metrics.clear();
  }
}

/**
 * 优化的展开状态管理Hook
 */
export const useOptimizedExpansion = () => {
  const monitor = PerformanceMonitor.getInstance();
  const expansionCountRef = useRef(0);
  
  // 节流的布局更新函数
  const throttledLayoutUpdate = useMemo(
    () => throttle((callback: () => void) => {
      const endMeasure = monitor.startMeasure('layout-update');
      callback();
      endMeasure();
    }, PERFORMANCE_CONFIG.LAYOUT_THROTTLE_MS),
    [monitor]
  );

  // 防抖的API调用函数
  const debouncedApiCall = useMemo(
    () => debounce(async (apiFunction: () => Promise<any>) => {
      const endMeasure = monitor.startMeasure('api-call');
      try {
        const result = await apiFunction();
        endMeasure();
        return result;
      } catch (error) {
        endMeasure();
        throw error;
      }
    }, PERFORMANCE_CONFIG.API_DEBOUNCE_MS),
    [monitor]
  );

  // 检查是否可以展开更多子工作流
  const canExpandMore = useCallback(() => {
    return expansionCountRef.current < PERFORMANCE_CONFIG.MAX_EXPANDED_SUBWORKFLOWS;
  }, []);

  // 更新展开计数
  const updateExpansionCount = useCallback((delta: number) => {
    expansionCountRef.current = Math.max(0, expansionCountRef.current + delta);
  }, []);

  return {
    throttledLayoutUpdate,
    debouncedApiCall,
    canExpandMore,
    updateExpansionCount,
    currentExpansionCount: () => expansionCountRef.current
  };
};

/**
 * 虚拟化渲染Hook - 用于大量子工作流节点
 */
export const useVirtualizedNodes = (nodes: any[], containerHeight: number = 400) => {
  const visibleNodes = useMemo(() => {
    if (nodes.length <= PERFORMANCE_CONFIG.VIRTUALIZATION_THRESHOLD) {
      return nodes;
    }

    // 简单的虚拟化逻辑 - 只渲染可见区域的节点
    const itemHeight = 150; // 节点高度
    const visibleCount = Math.ceil(containerHeight / itemHeight) + 2; // 多渲染2个作为缓冲
    
    return nodes.slice(0, visibleCount);
  }, [nodes, containerHeight]);

  const hasVirtualization = nodes.length > PERFORMANCE_CONFIG.VIRTUALIZATION_THRESHOLD;

  return {
    visibleNodes,
    hasVirtualization,
    totalCount: nodes.length,
    visibleCount: visibleNodes.length
  };
};

/**
 * 内存使用优化Hook
 */
export const useMemoryOptimization = () => {
  const cacheRef = useRef(new Map<string, { data: any; timestamp: number }>());

  // 清理过期缓存
  const cleanExpiredCache = useCallback(() => {
    const now = Date.now();
    const cache = cacheRef.current;
    
    const keysToDelete: string[] = [];
    cache.forEach((value, key) => {
      if (now - value.timestamp > PERFORMANCE_CONFIG.CACHE_EXPIRY_MS) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => cache.delete(key));
  }, []);

  // 设置缓存
  const setCache = useCallback((key: string, data: any) => {
    cleanExpiredCache();
    cacheRef.current.set(key, {
      data,
      timestamp: Date.now()
    });
  }, [cleanExpiredCache]);

  // 获取缓存
  const getCache = useCallback((key: string) => {
    const cached = cacheRef.current.get(key);
    if (!cached) return null;
    
    const now = Date.now();
    if (now - cached.timestamp > PERFORMANCE_CONFIG.CACHE_EXPIRY_MS) {
      cacheRef.current.delete(key);
      return null;
    }
    
    return cached.data;
  }, []);

  // 清理所有缓存
  const clearCache = useCallback(() => {
    cacheRef.current.clear();
  }, []);

  return {
    setCache,
    getCache,
    clearCache,
    cacheSize: () => cacheRef.current.size
  };
};

/**
 * 动画性能检测和自适应调整
 */
export const useAnimationPerformance = () => {
  const [performanceLevel, setPerformanceLevel] = useState(
    PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.HIGH
  );

  const monitor = PerformanceMonitor.getInstance();

  // 检测帧率并调整动画性能
  const checkFrameRate = useCallback(() => {
    let frameCount = 0;
    let lastTime = performance.now();

    const measureFrames = () => {
      frameCount++;
      const currentTime = performance.now();
      
      if (currentTime - lastTime >= 1000) { // 每秒检查一次
        const fps = frameCount;
        frameCount = 0;
        lastTime = currentTime;
        
        // 根据帧率调整动画性能级别
        if (fps < 30) {
          setPerformanceLevel(PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.LOW);
        } else if (fps < 45) {
          setPerformanceLevel(PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.MEDIUM);
        } else {
          setPerformanceLevel(PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.HIGH);
        }
        
        monitor.recordMetric('fps', fps);
      }
      
      requestAnimationFrame(measureFrames);
    };

    measureFrames();
  }, [monitor]);

  // 获取当前应该使用的动画配置
  const getAnimationConfig = useCallback(() => {
    switch (performanceLevel) {
      case PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.LOW:
        return {
          duration: 100,
          easing: 'linear',
          enableParticles: false,
          enableBlur: false
        };
      case PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.MEDIUM:
        return {
          duration: 200,
          easing: 'ease',
          enableParticles: false,
          enableBlur: true
        };
      case PERFORMANCE_CONFIG.ANIMATION_PERFORMANCE.HIGH:
        return {
          duration: 300,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          enableParticles: true,
          enableBlur: true
        };
      default:
        return {
          duration: 0,
          easing: 'none',
          enableParticles: false,
          enableBlur: false
        };
    }
  }, [performanceLevel]);

  return {
    performanceLevel,
    getAnimationConfig,
    checkFrameRate
  };
};

/**
 * 整体性能报告工具
 */
export const generatePerformanceReport = () => {
  const monitor = PerformanceMonitor.getInstance();
  
  const report = {
    timestamp: new Date().toISOString(),
    metrics: {
      layoutUpdate: monitor.getMetricStats('layout-update'),
      apiCall: monitor.getMetricStats('api-call'),
      fps: monitor.getMetricStats('fps'),
      nodeExpansion: monitor.getMetricStats('node-expansion'),
      renderTime: monitor.getMetricStats('render-time')
    },
    recommendations: [] as string[]
  };

  // 生成性能建议
  const layoutStats = report.metrics.layoutUpdate;
  if (layoutStats && layoutStats.avg > 50) {
    report.recommendations.push('布局更新较慢，建议减少同时展开的子工作流数量');
  }

  const apiStats = report.metrics.apiCall;
  if (apiStats && apiStats.avg > 1000) {
    report.recommendations.push('API调用响应较慢，建议增加缓存或优化网络请求');
  }

  const fpsStats = report.metrics.fps;
  if (fpsStats && fpsStats.avg < 30) {
    report.recommendations.push('动画帧率较低，建议降低动画复杂度或禁用部分特效');
  }

  return report;
};