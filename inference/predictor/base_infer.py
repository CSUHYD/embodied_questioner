from abc import ABC, abstractmethod

class BaseServer(ABC):
    
    @abstractmethod
    def chat(self, message):
        """
        处理传入的消息，并返回响应。
        
        参数:
            message (str): 用户发送的消息。
            
        返回:
            str: 对用户消息的回复。
        """
        pass

    @abstractmethod
    def generate(self, prompt):
        """
        根据提供的提示生成一些内容。
        
        参数:
            prompt (str): 用来生成内容的提示或上下文。
            
        返回:
            str: 根据提示生成的内容。
        """
        pass