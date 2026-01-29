// ============================================
// Error Types
// ============================================

export type ErrorType = 'connection' | 'api' | 'parse' | 'unknown';

export interface AppError {
    type: ErrorType;
    message: string;
    details?: string;
    timestamp: Date;
}

export function createError(type: ErrorType, message: string, details?: string): AppError {
    return {
        type,
        message,
        details,
        timestamp: new Date()
    };
}

export function getErrorMessage(error: unknown): string {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
        return '백엔드 서버에 연결할 수 없습니다. 서버 상태를 확인하세요.';
    }
    if (error instanceof Error) {
        return error.message;
    }
    return '알 수 없는 오류가 발생했습니다.';
}

export function getErrorType(error: unknown): ErrorType {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
        return 'connection';
    }
    if (error instanceof SyntaxError) {
        return 'parse';
    }
    return 'unknown';
}
