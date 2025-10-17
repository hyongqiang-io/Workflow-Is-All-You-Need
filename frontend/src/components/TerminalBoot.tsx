/**
 * 终端启动动画组件
 * 用于显示Matrix风格的系统启动序列
 */

import React, { useState, useEffect, ReactNode } from 'react';
import './terminal.css';

interface TerminalBootProps {
  children: ReactNode;
  bootSequence?: string[];
  onBootComplete?: () => void;
  duration?: number;
}

const defaultBootSequence = [
  'MATRIX PROTOCOL v3.14.159',
  'Initializing neural pathways...',
  'Loading quantum encryption keys...',
  'Establishing secure connection...',
  'Handshake complete.',
  'Welcome to the Matrix.',
  '',
  'SYSTEM READY.'
];

export const TerminalBoot: React.FC<TerminalBootProps> = ({
  children,
  bootSequence = defaultBootSequence,
  onBootComplete,
  duration = 800
}) => {
  const [currentLine, setCurrentLine] = useState(0);
  const [displayedText, setDisplayedText] = useState('');
  const [isBooting, setIsBooting] = useState(true);
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    if (!isBooting) return;

    const animate = () => {
      if (currentLine < bootSequence.length) {
        const text = bootSequence[currentLine];
        setDisplayedText(text);

        setTimeout(() => {
          setCurrentLine(currentLine + 1);
        }, duration);
      } else {
        // 启动完成
        setTimeout(() => {
          setIsBooting(false);
          setShowContent(true);
          onBootComplete?.();
        }, 1000);
      }
    };

    animate();
  }, [currentLine, bootSequence, duration, isBooting, onBootComplete]);

  if (!isBooting && showContent) {
    return <>{children}</>;
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      backgroundColor: 'var(--color-terminal-black)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 9999,
      fontFamily: 'var(--font-mono)',
      color: 'var(--color-matrix-primary)',
    }}>
      {/* Matrix雨背景效果 */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        opacity: 0.1,
        background: `
          linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, 0.3) 25%, rgba(0, 255, 0, 0.3) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.3) 75%, rgba(0, 255, 0, 0.3) 76%, transparent 77%, transparent),
          linear-gradient(90deg, transparent 24%, rgba(0, 255, 0, 0.3) 25%, rgba(0, 255, 0, 0.3) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.3) 75%, rgba(0, 255, 0, 0.3) 76%, transparent 77%, transparent)
        `,
        backgroundSize: '4px 4px',
        animation: 'matrix-rain 20s linear infinite',
      }} />

      {/* 启动文本显示区域 */}
      <div style={{
        position: 'relative',
        maxWidth: '600px',
        padding: '40px',
        border: '1px solid var(--color-border-primary)',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        boxShadow: 'var(--shadow-glow-md)',
      }}>
        {/* 终端头部 */}
        <div style={{
          marginBottom: '24px',
          padding: '12px',
          borderBottom: '1px solid var(--color-border-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-status-error)',
          }} />
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-status-warning)',
          }} />
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-status-success)',
          }} />
          <span style={{
            marginLeft: '12px',
            fontSize: '12px',
            color: 'var(--color-text-secondary)',
          }}>
            matrix://boot_sequence
          </span>
        </div>

        {/* 启动序列显示 */}
        <div style={{
          minHeight: '200px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}>
          {bootSequence.slice(0, currentLine).map((line, index) => (
            <div
              key={index}
              style={{
                fontSize: '14px',
                fontFamily: 'var(--font-mono)',
                color: index === currentLine - 1 ? 'var(--color-matrix-primary)' : 'var(--color-text-secondary)',
                textShadow: index === currentLine - 1 ? '0 0 4px currentColor' : 'none',
                opacity: index === currentLine - 1 ? 1 : 0.7,
                animation: index === currentLine - 1 ? 'matrix-glow 1s ease-in-out infinite' : 'none',
              }}
            >
              {line && (
                <>
                  <span style={{ color: 'var(--color-text-tertiary)' }}>{'>'} </span>
                  <span className={index === currentLine - 1 ? 'typewriter' : ''}>
                    {line}
                  </span>
                  {index === currentLine - 1 && (
                    <span className="terminal-cursor" style={{
                      width: '8px',
                      height: '14px',
                      marginLeft: '4px',
                    }}></span>
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        {/* 进度指示器 */}
        <div style={{
          marginTop: '24px',
          padding: '12px 0',
          borderTop: '1px solid var(--color-border-muted)',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontSize: '11px',
            color: 'var(--color-text-tertiary)',
          }}>
            <span>PROGRESS:</span>
            <div style={{
              flex: 1,
              height: '4px',
              backgroundColor: 'var(--color-border-muted)',
              borderRadius: '2px',
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${(currentLine / bootSequence.length) * 100}%`,
                height: '100%',
                backgroundColor: 'var(--color-matrix-primary)',
                transition: 'width 0.3s ease',
                boxShadow: '0 0 4px var(--color-matrix-primary)',
              }} />
            </div>
            <span>{Math.round((currentLine / bootSequence.length) * 100)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TerminalBoot;