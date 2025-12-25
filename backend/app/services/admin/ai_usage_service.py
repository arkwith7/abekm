"""
AI 사용량 추적 서비스
LLM API 호출을 기록하고 통계를 제공
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.models.core.ai_usage_models import TbAiUsageLog, TbAiModelConfig

logger = logging.getLogger(__name__)


class AIUsageService:
    """AI 사용량 추적 및 통계 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_usage(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        user_id: Optional[int] = None,
        user_emp_no: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> TbAiUsageLog:
        """AI 사용 로그 기록"""
        try:
            # 총 토큰 수 계산
            total_tokens = None
            if input_tokens is not None or output_tokens is not None:
                total_tokens = (input_tokens or 0) + (output_tokens or 0)
            
            # 비용 계산
            estimated_cost = await self._calculate_cost(
                provider, model, input_tokens, output_tokens
            )
            
            # 로그 생성
            usage_log = TbAiUsageLog(
                user_id=user_id,
                user_emp_no=user_emp_no,
                session_id=session_id,
                provider=provider,
                model=model,
                operation=operation,
                endpoint=endpoint,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                latency_ms=latency_ms,
                success=success,
                error_code=error_code,
                error_message=error_message,
                request_metadata=request_metadata
            )
            
            self.db.add(usage_log)
            await self.db.commit()
            await self.db.refresh(usage_log)
            
            logger.debug(f"AI 사용 로그 기록: {provider}/{model} - {total_tokens} tokens")
            return usage_log
            
        except Exception as e:
            logger.error(f"AI 사용 로그 기록 실패: {e}")
            await self.db.rollback()
            raise
    
    async def _calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int]
    ) -> Optional[Decimal]:
        """토큰 사용량 기반 비용 계산"""
        if input_tokens is None and output_tokens is None:
            return None
        
        try:
            # 모델 비용 설정 조회
            config_result = await self.db.execute(
                select(TbAiModelConfig).where(
                    and_(
                        TbAiModelConfig.provider == provider,
                        TbAiModelConfig.model == model,
                        TbAiModelConfig.is_active == True
                    )
                )
            )
            config = config_result.scalar_one_or_none()
            
            if not config:
                # 비슷한 모델명 검색 (부분 매칭)
                config_result = await self.db.execute(
                    select(TbAiModelConfig).where(
                        and_(
                            TbAiModelConfig.provider == provider,
                            TbAiModelConfig.model.ilike(f"%{model.split(':')[0]}%"),
                            TbAiModelConfig.is_active == True
                        )
                    ).limit(1)
                )
                config = config_result.scalar_one_or_none()
            
            if not config:
                return None
            
            # 비용 계산 (1K 토큰당 비용)
            input_cost = Decimal(0)
            output_cost = Decimal(0)
            
            if input_tokens and config.input_cost_per_1k:
                input_cost = Decimal(input_tokens) / 1000 * config.input_cost_per_1k
            
            if output_tokens and config.output_cost_per_1k:
                output_cost = Decimal(output_tokens) / 1000 * config.output_cost_per_1k
            
            return input_cost + output_cost
            
        except Exception as e:
            logger.warning(f"비용 계산 실패: {e}")
            return None
    
    async def get_usage_summary(
        self,
        days: int = 30,
        user_emp_no: Optional[str] = None
    ) -> Dict[str, Any]:
        """AI 사용량 요약 통계"""
        start_date = datetime.now() - timedelta(days=days)
        
        # 기본 필터
        filters = [TbAiUsageLog.created_at >= start_date]
        if user_emp_no:
            filters.append(TbAiUsageLog.user_emp_no == user_emp_no)
        
        # 전체 통계
        total_result = await self.db.execute(
            select(
                func.count(TbAiUsageLog.id).label('total_requests'),
                func.sum(TbAiUsageLog.input_tokens).label('total_input_tokens'),
                func.sum(TbAiUsageLog.output_tokens).label('total_output_tokens'),
                func.sum(TbAiUsageLog.total_tokens).label('total_tokens'),
                func.sum(TbAiUsageLog.estimated_cost_usd).label('total_cost'),
                func.avg(TbAiUsageLog.latency_ms).label('avg_latency'),
                func.count(TbAiUsageLog.id).filter(TbAiUsageLog.success == True).label('success_count'),
                func.count(TbAiUsageLog.id).filter(TbAiUsageLog.success == False).label('failure_count')
            ).where(and_(*filters))
        )
        total_row = total_result.one()
        
        # 제공자별 통계
        provider_result = await self.db.execute(
            select(
                TbAiUsageLog.provider,
                func.count(TbAiUsageLog.id).label('requests'),
                func.sum(TbAiUsageLog.total_tokens).label('tokens'),
                func.sum(TbAiUsageLog.estimated_cost_usd).label('cost')
            ).where(and_(*filters))
            .group_by(TbAiUsageLog.provider)
        )
        by_provider = [
            {
                "provider": row.provider,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost) if row.cost else 0
            }
            for row in provider_result.all()
        ]
        
        # 작업별 통계
        operation_result = await self.db.execute(
            select(
                TbAiUsageLog.operation,
                func.count(TbAiUsageLog.id).label('requests'),
                func.sum(TbAiUsageLog.total_tokens).label('tokens')
            ).where(and_(*filters))
            .group_by(TbAiUsageLog.operation)
        )
        by_operation = [
            {
                "operation": row.operation,
                "requests": row.requests,
                "tokens": row.tokens or 0
            }
            for row in operation_result.all()
        ]
        
        return {
            "period_days": days,
            "summary": {
                "total_requests": total_row.total_requests or 0,
                "total_input_tokens": total_row.total_input_tokens or 0,
                "total_output_tokens": total_row.total_output_tokens or 0,
                "total_tokens": total_row.total_tokens or 0,
                "total_cost_usd": float(total_row.total_cost) if total_row.total_cost else 0,
                "avg_latency_ms": float(total_row.avg_latency) if total_row.avg_latency else 0,
                "success_count": total_row.success_count or 0,
                "failure_count": total_row.failure_count or 0,
                "success_rate": (
                    (total_row.success_count / total_row.total_requests * 100)
                    if total_row.total_requests > 0 else 0
                )
            },
            "by_provider": by_provider,
            "by_operation": by_operation
        }
    
    async def get_daily_usage(
        self,
        days: int = 30,
        user_emp_no: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """일별 AI 사용량 통계"""
        start_date = datetime.now() - timedelta(days=days)
        
        filters = [TbAiUsageLog.created_at >= start_date]
        if user_emp_no:
            filters.append(TbAiUsageLog.user_emp_no == user_emp_no)
        
        result = await self.db.execute(
            select(
                func.date(TbAiUsageLog.created_at).label('date'),
                func.count(TbAiUsageLog.id).label('requests'),
                func.sum(TbAiUsageLog.total_tokens).label('tokens'),
                func.sum(TbAiUsageLog.estimated_cost_usd).label('cost')
            ).where(and_(*filters))
            .group_by(func.date(TbAiUsageLog.created_at))
            .order_by(func.date(TbAiUsageLog.created_at))
        )
        
        return [
            {
                "date": str(row.date),
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost) if row.cost else 0
            }
            for row in result.all()
        ]
    
    async def get_top_users(
        self,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """상위 AI 사용자 목록"""
        start_date = datetime.now() - timedelta(days=days)
        
        result = await self.db.execute(
            select(
                TbAiUsageLog.user_emp_no,
                func.count(TbAiUsageLog.id).label('requests'),
                func.sum(TbAiUsageLog.total_tokens).label('tokens'),
                func.sum(TbAiUsageLog.estimated_cost_usd).label('cost')
            ).where(
                and_(
                    TbAiUsageLog.created_at >= start_date,
                    TbAiUsageLog.user_emp_no.isnot(None)
                )
            )
            .group_by(TbAiUsageLog.user_emp_no)
            .order_by(desc(func.sum(TbAiUsageLog.total_tokens)))
            .limit(limit)
        )
        
        return [
            {
                "user_emp_no": row.user_emp_no,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost) if row.cost else 0
            }
            for row in result.all()
        ]
    
    async def get_model_configs(self) -> List[Dict[str, Any]]:
        """AI 모델 설정 목록 조회"""
        result = await self.db.execute(
            select(TbAiModelConfig).where(TbAiModelConfig.is_active == True)
            .order_by(TbAiModelConfig.provider, TbAiModelConfig.model)
        )
        
        return [
            {
                "id": config.id,
                "provider": config.provider,
                "model": config.model,
                "display_name": config.display_name,
                "input_cost_per_1k": float(config.input_cost_per_1k) if config.input_cost_per_1k else None,
                "output_cost_per_1k": float(config.output_cost_per_1k) if config.output_cost_per_1k else None,
                "max_tokens_per_request": config.max_tokens_per_request,
                "max_requests_per_minute": config.max_requests_per_minute
            }
            for config in result.scalars().all()
        ]

