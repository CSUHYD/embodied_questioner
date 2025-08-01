"""
SessionManager - 机器人会话管理系统

统一管理机器人执行过程中的所有信息，包括：
- 问答历史 (QA History)
- 执行记录 (Execution Records) 
- 失败记录 (Failure Records)
- 会话统计信息

设计原则：
1. 低耦合：其他类通过RobotController统一访问SessionManager
2. 数据一致性：所有会话数据统一管理
3. 可扩展性：支持未来添加新的记录类型
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class QARecord:
    """问答记录"""
    timestamp: str
    question: str
    answer: str
    context: Optional[str] = None  # 问题产生的上下文
    round_number: int = 0
    question_type: str = "general"  # general, clarification, verification, decision


@dataclass
class ExecutionRecord:
    """执行记录"""
    timestamp: str
    action_type: str
    action_params: Dict[str, Any]
    result: str
    success: bool
    round_number: int = 0
    object_id: Optional[str] = None
    scene_info: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[int] = None


@dataclass
class FailureRecord:
    """失败记录"""
    timestamp: str
    failure_type: str  # search_failure, navigation_failure, action_failure, verification_failure
    description: str
    context: Dict[str, Any]
    round_number: int = 0
    recovery_attempted: bool = False
    recovery_successful: bool = False


class SessionManager:
    """会话管理器 - 统一管理机器人执行过程中的所有信息"""
    
    def __init__(self, session_id: Optional[str] = None, save_path: Optional[str] = None):
        self.session_id = session_id or self._generate_session_id()
        self.save_path = save_path or self._get_default_save_path()
        
        # 确保保存目录存在
        os.makedirs(self.save_path, exist_ok=True)
        
        # 初始化记录列表
        self.qa_history: List[QARecord] = []
        self.execution_records: List[ExecutionRecord] = []
        self.failure_records: List[FailureRecord] = []
        
        # 会话统计信息
        self.session_start_time = self._get_timestamp()
        self.current_round = 0
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions = 0
        
        logging.info(f"[SESSION] Initialized SessionManager with ID: {self.session_id}")
    
    def _generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _get_default_save_path(self) -> str:
        """获取默认保存路径"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "session_logs")
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ==================== QA History Management ====================
    
    def add_qa_record(self, question: str, answer: str, context: Optional[str] = None, 
                     question_type: str = "general") -> None:
        """添加问答记录"""
        record = QARecord(
            timestamp=self._get_timestamp(),
            question=question,
            answer=answer,
            context=context,
            round_number=self.current_round,
            question_type=question_type
        )
        self.qa_history.append(record)
        logging.info(f"[SESSION] Added QA record: {question_type} question")
    
    def get_qa_history_string(self, max_pairs: int = 10) -> str:
        """获取格式化的问答历史字符串"""
        if not self.qa_history:
            return ""
        
        recent_history = self.get_recent_qa_history(max_pairs)
        history_lines = []
        
        for record in recent_history:
            history_lines.append(f"Q: {record.question}")
            history_lines.append(f"A: {record.answer}")
        
        return "\n".join(history_lines)
    
    def get_recent_qa_history(self, count: int = 5) -> List[QARecord]:
        """获取最近的问答历史"""
        return self.qa_history[-count:] if count > 0 else self.qa_history
    
    def clear_qa_history(self) -> None:
        """清空问答历史"""
        self.qa_history.clear()
        logging.info("[SESSION] Cleared QA history")
    
    # ==================== Execution Records Management ====================
    
    def add_execution_record(self, action_type: str, action_params: Dict[str, Any], 
                           result: str, success: bool, object_id: Optional[str] = None,
                           scene_info: Optional[Dict[str, Any]] = None,
                           execution_time_ms: Optional[int] = None) -> None:
        """添加执行记录"""
        record = ExecutionRecord(
            timestamp=self._get_timestamp(),
            action_type=action_type,
            action_params=action_params,
            result=result,
            success=success,
            round_number=self.current_round,
            object_id=object_id,
            scene_info=scene_info,
            execution_time_ms=execution_time_ms
        )
        self.execution_records.append(record)
        
        # 更新统计信息
        self.total_actions += 1
        if success:
            self.successful_actions += 1
        else:
            self.failed_actions += 1
        
        logging.info(f"[SESSION] Added execution record: {action_type} ({'success' if success else 'failed'})")
    
    def get_execution_history_summary(self, max_actions: int = 10) -> str:
        """获取执行历史摘要"""
        if not self.execution_records:
            return "No execution records available"
        
        recent_records = self.execution_records[-max_actions:] if max_actions > 0 else self.execution_records
        history_lines = []
        
        for i, record in enumerate(recent_records, 1):
            status = "✓" if record.success else "✗"
            action_desc = f"{record.action_type}"
            
            # 添加对象信息
            if record.action_params:
                if 'object_type' in record.action_params:
                    action_desc += f" {record.action_params['object_type']}"
                elif 'objectType' in record.action_params:
                    action_desc += f" {record.action_params['objectType']}"
            
            history_lines.append(f"{i}. {status} {action_desc} - {record.result}")
        
        return "\n".join(history_lines)
    
    # ==================== Failure Records Management ====================
    
    def add_failure_record(self, failure_type: str, description: str, 
                         context: Dict[str, Any], recovery_attempted: bool = False,
                         recovery_successful: bool = False) -> None:
        """添加失败记录"""
        record = FailureRecord(
            timestamp=self._get_timestamp(),
            failure_type=failure_type,
            description=description,
            context=context,
            round_number=self.current_round,
            recovery_attempted=recovery_attempted,
            recovery_successful=recovery_successful
        )
        self.failure_records.append(record)
        logging.info(f"[SESSION] Added failure record: {failure_type}")
    
    def get_failure_summary(self, max_failures: int = 5) -> str:
        """获取失败记录摘要"""
        if not self.failure_records:
            return "No failure records"
        
        recent_failures = self.failure_records[-max_failures:] if max_failures > 0 else self.failure_records
        summary_lines = []
        
        for i, record in enumerate(recent_failures, 1):
            recovery_info = ""
            if record.recovery_attempted:
                recovery_info = f" (Recovery: {'✓' if record.recovery_successful else '✗'})"
            
            summary_lines.append(f"{i}. {record.failure_type}: {record.description}{recovery_info}")
        
        return "\n".join(summary_lines)
    
    # ==================== Session Management ====================
    
    def start_new_round(self) -> None:
        """开始新的执行轮次"""
        self.current_round += 1
        logging.info(f"[SESSION] Started round {self.current_round}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        return {
            "session_id": self.session_id,
            "start_time": self.session_start_time,
            "current_round": self.current_round,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "total_qa_interactions": len(self.qa_history),
            "total_failures": len(self.failure_records),
            "success_rate": (self.successful_actions / max(self.total_actions, 1)) * 100
        }
    
    def save_session(self, filename: Optional[str] = None) -> str:
        """保存会话数据到文件"""
        if filename is None:
            filename = f"{self.session_id}.json"
        
        filepath = os.path.join(self.save_path, filename)
        
        session_data = {
            "session_info": self.get_session_stats(),
            "qa_history": [asdict(record) for record in self.qa_history],
            "execution_records": [asdict(record) for record in self.execution_records],
            "failure_records": [asdict(record) for record in self.failure_records]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"[SESSION] Saved session to: {filepath}")
        return filepath
    
    def load_session(self, filepath: str) -> bool:
        """从文件加载会话数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 恢复会话信息
            session_info = session_data.get("session_info", {})
            self.session_id = session_info.get("session_id", self.session_id)
            self.session_start_time = session_info.get("start_time", self.session_start_time)
            self.current_round = session_info.get("current_round", 0)
            self.total_actions = session_info.get("total_actions", 0)
            self.successful_actions = session_info.get("successful_actions", 0)
            self.failed_actions = session_info.get("failed_actions", 0)
            
            # 恢复记录
            self.qa_history = [QARecord(**record) for record in session_data.get("qa_history", [])]
            self.execution_records = [ExecutionRecord(**record) for record in session_data.get("execution_records", [])]
            self.failure_records = [FailureRecord(**record) for record in session_data.get("failure_records", [])]
            
            logging.info(f"[SESSION] Loaded session from: {filepath}")
            return True
            
        except Exception as e:
            logging.error(f"[SESSION] Failed to load session from {filepath}: {e}")
            return False
    
    def reset_session(self) -> None:
        """重置会话数据"""
        self.qa_history.clear()
        self.execution_records.clear()
        self.failure_records.clear()
        self.current_round = 0
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions = 0
        logging.info("[SESSION] Reset session data")
    
    def get_session_summary(self) -> str:
        """获取会话摘要"""
        stats = self.get_session_stats()
        recent_qa = self.get_recent_qa_history(3)
        recent_failures = self.failure_records[-3:] if self.failure_records else []
        
        summary_lines = [
            f"Session ID: {stats['session_id']}",
            f"Duration: {stats['start_time']} - {self._get_timestamp()}",
            f"Round: {stats['current_round']}",
            f"Actions: {stats['successful_actions']}/{stats['total_actions']} ({stats['success_rate']:.1f}% success)",
            f"QA Interactions: {stats['total_qa_interactions']}",
            f"Failures: {stats['total_failures']}"
        ]
        
        if recent_qa:
            summary_lines.append("\nRecent Q&A:")
            for qa in recent_qa:
                summary_lines.append(f"  Q: {qa.question[:50]}...")
                summary_lines.append(f"  A: {qa.answer[:50]}...")
        
        if recent_failures:
            summary_lines.append("\nRecent Failures:")
            for failure in recent_failures:
                summary_lines.append(f"  {failure.failure_type}: {failure.description[:50]}...")
        
        return "\n".join(summary_lines)