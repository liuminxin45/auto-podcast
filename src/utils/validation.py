"""
数据验证工具模块

提供严格的数据验证机制，确保 pipeline 各阶段的数据完整性。
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """数据验证失败异常"""
    pass


class StrictModeError(ValidationError):
    """严格模式下的验证失败异常"""
    pass


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    
    def raise_if_failed(self, strict: bool = False):
        """如果验证失败则抛出异常"""
        if not self.passed:
            error_msg = "\n".join(self.errors)
            if strict:
                raise StrictModeError(f"严格模式验证失败:\n{error_msg}")
            else:
                raise ValidationError(f"验证失败:\n{error_msg}")
        
        # 即使通过，也记录警告
        if self.warnings:
            for warning in self.warnings:
                logger.warning(f"验证警告: {warning}")


def validate_required_fields(
    data: Dict[str, Any],
    required_fields: Set[str],
    context: str = "",
    strict: bool = True
) -> ValidationResult:
    """
    验证字典中是否包含所有必需字段
    
    Args:
        data: 待验证的字典
        required_fields: 必需字段集合
        context: 上下文信息（用于错误消息）
        strict: 是否严格模式（严格模式下缺失字段会抛异常）
    
    Returns:
        ValidationResult
    """
    errors = []
    warnings = []
    
    missing_fields = required_fields - set(data.keys())
    
    if missing_fields:
        error_msg = f"缺少必需字段: {missing_fields}"
        if context:
            error_msg = f"{context} - {error_msg}"
        errors.append(error_msg)
    
    # 检查字段值是否为 None 或空
    empty_fields = []
    for field in required_fields:
        if field in data:
            value = data[field]
            if value is None or (isinstance(value, (str, list, dict)) and not value):
                empty_fields.append(field)
    
    if empty_fields:
        warning_msg = f"字段值为空: {empty_fields}"
        if context:
            warning_msg = f"{context} - {warning_msg}"
        warnings.append(warning_msg)
    
    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_field_types(
    data: Dict[str, Any],
    field_types: Dict[str, type],
    context: str = "",
    strict: bool = True
) -> ValidationResult:
    """
    验证字典中字段的类型
    
    Args:
        data: 待验证的字典
        field_types: 字段类型映射 {field_name: expected_type}
        context: 上下文信息
        strict: 是否严格模式
    
    Returns:
        ValidationResult
    """
    errors = []
    warnings = []
    
    for field, expected_type in field_types.items():
        if field not in data:
            continue
        
        value = data[field]
        if value is None:
            continue
        
        if not isinstance(value, expected_type):
            error_msg = f"字段 '{field}' 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}"
            if context:
                error_msg = f"{context} - {error_msg}"
            errors.append(error_msg)
    
    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_evidence_pack(
    evidence_pack: Dict[str, Any],
    strict: bool = True
) -> ValidationResult:
    """
    验证 EvidencePack 数据结构
    
    Args:
        evidence_pack: EvidencePack 字典
        strict: 是否严格模式
    
    Returns:
        ValidationResult
    """
    # 必需字段
    required_fields = {
        "item_id",
        "claim",
        "main_query",
        "summary",
        "verdict",
        "confidence"
    }
    
    # 字段类型
    field_types = {
        "item_id": str,
        "claim": dict,
        "main_query": dict,
        "main_evidence": list,
        "contrast_evidence": list,
        "summary": str,
        "verdict": str,
        "confidence": (int, float),
        "metadata": dict
    }
    
    # 验证必需字段
    result1 = validate_required_fields(
        evidence_pack,
        required_fields,
        context="EvidencePack",
        strict=strict
    )
    
    # 验证字段类型
    result2 = validate_field_types(
        evidence_pack,
        field_types,
        context="EvidencePack",
        strict=strict
    )
    
    # 合并结果
    return ValidationResult(
        passed=result1.passed and result2.passed,
        errors=result1.errors + result2.errors,
        warnings=result1.warnings + result2.warnings
    )


def validate_enhanced_item(
    item: Dict[str, Any],
    require_research: bool = True,
    strict: bool = True
) -> ValidationResult:
    """
    验证 Enhanced Item 数据结构
    
    Args:
        item: Enhanced Item 字典
        require_research: 是否要求包含 research 数据
        strict: 是否严格模式
    
    Returns:
        ValidationResult
    """
    errors = []
    warnings = []
    
    # 基础必需字段
    required_fields = {"id", "title", "source_name"}
    
    # 验证基础字段
    result = validate_required_fields(
        item,
        required_fields,
        context="Enhanced Item",
        strict=strict
    )
    errors.extend(result.errors)
    warnings.extend(result.warnings)
    
    # 如果要求 research 数据
    if require_research:
        research_fields = {
            "research_evidence",
            "research_claims",
            "research_verdict",
            "research_confidence"
        }
        
        missing_research = research_fields - set(item.keys())
        if missing_research:
            errors.append(f"Enhanced Item 缺少 research 字段: {missing_research}")
        
        # 检查 research 数据是否为空
        if "research_evidence" in item:
            if not item["research_evidence"]:
                warnings.append(f"Item {item.get('id')} 的 research_evidence 为空")
        
        if "research_claims" in item:
            if not item["research_claims"]:
                warnings.append(f"Item {item.get('id')} 的 research_claims 为空")
    
    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_batch(
    items: List[Dict[str, Any]],
    validator_func: callable,
    context: str = "",
    fail_fast: bool = False,
    strict: bool = True
) -> ValidationResult:
    """
    批量验证数据
    
    Args:
        items: 待验证的数据列表
        validator_func: 验证函数
        context: 上下文信息
        fail_fast: 是否遇到第一个错误就停止
        strict: 是否严格模式
    
    Returns:
        ValidationResult
    """
    all_errors = []
    all_warnings = []
    
    for i, item in enumerate(items):
        result = validator_func(item, strict=strict)
        
        if result.errors:
            for error in result.errors:
                all_errors.append(f"[{i}] {error}")
            
            if fail_fast:
                break
        
        all_warnings.extend(result.warnings)
    
    summary = f"{context} - 验证 {len(items)} 项数据"
    if all_errors:
        summary += f", {len(all_errors)} 个错误"
    if all_warnings:
        summary += f", {len(all_warnings)} 个警告"
    
    logger.info(summary)
    
    return ValidationResult(
        passed=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings
    )
