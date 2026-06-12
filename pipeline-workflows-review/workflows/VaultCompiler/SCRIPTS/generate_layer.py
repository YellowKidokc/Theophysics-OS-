from __future__ import annotations
from engines.pipeline.llm_hub import LLMHub
hub=LLMHub(queue_dir='_queue')

def _submit(prompt,text,backend='ollama'):
    return hub.submit('vault-compiler','inline',prompt_name=prompt,backend=backend,priority='standard',input_text=text[:7000])
def generate_executive_summary(text:str)->str: return _submit('executive_summary',text,'ollama')
def generate_plain_english(text:str)->str: return _submit('plain_language',text,'ollama')
def generate_academic_summary(text:str)->str: return _submit('academic_summary',text,'claude_api')
def generate_framework_impact(text:str,framework_data:dict)->str: return _submit('framework_impact',text+"\n"+str(framework_data),'claude_api')
def generate_open_obligations(text:str)->str: return _submit('framework_impact',text,'claude_api')
