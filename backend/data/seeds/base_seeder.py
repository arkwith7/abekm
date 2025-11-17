"""
Base Seeder

모든 시더의 기본 클래스입니다.
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text, Integer, Boolean, DateTime, String, Text, Float
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
import logging

logger = logging.getLogger(__name__)


class BaseSeeder:
    """시더 베이스 클래스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.data_dir = Path(__file__).parent.parent / "csv"
    
    async def load_csv(self, filename: str) -> List[Dict[str, Any]]:
        """CSV 파일을 로드하여 딕셔너리 리스트로 반환합니다."""
        csv_path = self.data_dir / filename
        
        if not csv_path.exists():
            logger.warning(f"⚠️  CSV 파일을 찾을 수 없습니다: {csv_path}")
            return []
        
        data = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 빈 값을 None으로 변환
                    cleaned_row = {k: (v if v.strip() else None) for k, v in row.items()}
                    data.append(cleaned_row)
            
            logger.info(f"✅ {filename} 로드 완료: {len(data)}개 레코드")
            return data
            
        except Exception as e:
            logger.error(f"❌ CSV 파일 로드 실패 ({filename}): {e}")
            return []
    
    async def clear_table(self, table_name: str) -> bool:
        """테이블의 모든 데이터를 삭제합니다."""
        try:
            await self.session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            await self.session.commit()
            logger.info(f"🗑️  {table_name} 테이블 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"❌ {table_name} 테이블 초기화 실패: {e}")
            await self.session.rollback()
            return False
    
    async def get_record_count(self, table_name: str) -> int:
        """테이블의 레코드 수를 반환합니다."""
        try:
            result = await self.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.warning(f"⚠️  {table_name} 레코드 수 조회 실패: {e}")
            return 0
    
    async def table_exists(self, table_name: str) -> bool:
        """테이블이 존재하는지 확인합니다."""
        try:
            result = await self.session.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"),
                {"table_name": table_name}
            )
            exists = result.scalar()
            return exists or False
        except Exception as e:
            logger.warning(f"⚠️  {table_name} 존재 여부 확인 실패: {e}")
            return False
    
    async def is_table_empty(self, table_name: str) -> bool:
        """테이블이 비어있는지 확인합니다."""
        count = await self.get_record_count(table_name)
        return count == 0
    
    def _convert_value(self, value: Any, python_type) -> Any:
        """CSV 문자열을 파이썬 타입에 맞게 변환합니다."""
        if value is None or value == '':
            return None
        
        # Integer 타입 (int)
        if python_type == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.warning(f"⚠️  Integer 변환 실패: {value}")
                return None
        
        # Boolean 타입 (bool)
        if python_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.upper() in ('Y', 'YES', 'TRUE', '1', 'T')
            return bool(value)
        
        # DateTime 타입 (datetime)
        if python_type == datetime:
            if isinstance(value, datetime):
                return value
            try:
                # ISO 8601 형식 시도
                return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except (ValueError, TypeError):
                try:
                    # 일반적인 형식 시도
                    return datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    logger.warning(f"⚠️  DateTime 변환 실패: {value}")
                    return None
        
        # Float 타입 (float)
        if python_type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.warning(f"⚠️  Float 변환 실패: {value}")
                return None
        
        # String/Text 타입은 그대로 반환 (str)
        return value
    
    def _prepare_row_data(self, row: Dict[str, Any], model) -> Dict[str, Any]:
        """모델의 컬럼 타입에 맞게 row 데이터를 변환합니다."""
        prepared_data = {}
        mapper = inspect(model)
        
        for key, value in row.items():
            # 모델에 해당 컬럼이 있는지 확인
            if key not in mapper.columns:
                logger.warning(f"⚠️  모델 {model.__name__}에 컬럼 '{key}'이 없습니다. 스킵합니다.")
                continue
            
            # 컬럼 타입 확인 (파이썬 타입으로 변환)
            column = mapper.columns[key]
            try:
                python_type = column.type.python_type
            except NotImplementedError:
                # 일부 타입은 python_type이 없을 수 있음
                python_type = str
            
            # 타입 변환
            prepared_data[key] = self._convert_value(value, python_type)
        
        return prepared_data
    
    async def run_seed(
        self,
        csv_filename: str,
        model,
        key_fields: List[str],
        required_fields: Optional[List[str]] = None,
        clear_existing: bool = False
    ) -> bool:
        """CSV 파일에서 데이터를 로드하여 DB에 저장합니다."""
        try:
            table_name = model.__tablename__
            
            # 기존 데이터 삭제
            if clear_existing:
                await self.clear_table(table_name)
            
            # CSV 로드
            data = await self.load_csv(csv_filename)
            if not data:
                logger.warning(f"⚠️  {csv_filename}에 데이터가 없습니다.")
                return True
            
            # 데이터 삽입
            inserted_count = 0
            skipped_count = 0
            
            for row in data:
                try:
                    # 필수 필드 검증
                    if required_fields:
                        missing_fields = [f for f in required_fields if not row.get(f)]
                        if missing_fields:
                            logger.warning(f"⚠️  필수 필드 누락: {missing_fields} in {row}")
                            skipped_count += 1
                            continue
                    
                    # 타입 변환
                    prepared_row = self._prepare_row_data(row, model)
                    
                    # 모델 인스턴스 생성
                    instance = model(**prepared_row)
                    self.session.add(instance)
                    inserted_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️  레코드 삽입 실패: {row} - {e}")
                    skipped_count += 1
            
            # 커밋
            await self.session.commit()
            logger.info(f"✅ {table_name}: {inserted_count}개 삽입, {skipped_count}개 스킵")
            return True
            
        except Exception as e:
            logger.error(f"❌ {csv_filename} 시드 실패: {e}")
            await self.session.rollback()
            return False
