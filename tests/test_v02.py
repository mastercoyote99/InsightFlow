import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ollama_deep_researcher.sources import merge_sources, check_citations, normalize_url

class SourcesTest(unittest.TestCase):
    def test_stable_ids_and_new_snippets(self):
        a = {'url':'https://example.com/a','title':'same','content':'first'}
        first, _ = merge_sources([], [a], 1)
        second, context = merge_sources(first, [dict(a, title='changed', content='new'),dict(a,url='https://example.com/b')], 2)
        self.assertEqual([x['id'] for x in second], ['S1','S2'])
        self.assertEqual(len(second[0]['observations']),2)
        self.assertEqual(len(first[0]['observations']),1)
        self.assertIn('new', context)
    def test_invalid_and_missing(self):
        r,_ = merge_sources([], [{'url':'https://example.com','title':'a','content':'b'}],1)
        self.assertEqual(check_citations('[S999]',r)['unknown_ids'],['S999'])
        self.assertTrue(check_citations('none',r)['missing_citations'])
        self.assertEqual(check_citations('[S1]',r)['status'],'passed')
        self.assertEqual(check_citations('[S1] https://example.com',r)['status'],'warning')
    def test_empty(self):
        with self.assertRaises(ValueError): merge_sources([],[],1)
    def test_conservative_urls(self):
        self.assertEqual(normalize_url('https://EXAMPLE.com/a#x'),'https://example.com/a')
        self.assertNotEqual(normalize_url('https://example.com/a?v=1'),normalize_url('https://example.com/a?v=2'))
    def test_recorded_replay(self):
        registry=[]; count=0
        path=Path(__file__).parent/'fixtures'/'two-loops-events.jsonl'
        for line in path.read_text(encoding='utf-8').splitlines():
            e=json.loads(line)
            if e['node']!='web_research':continue
            results=[]
            for chunk in e['update']['web_research_results'][0].split('Source: ')[1:]:
                title,rest=chunk.split('\n===\nURL: ',1)
                url,rest=rest.split('\n===\nMost relevant content from source: ',1)
                results.append({'title':title,'url':url,'content':rest.split('\n===')[0]})
            count+=len(results)
            registry,_=merge_sources(registry,results,e['update']['research_loop_count'])
        self.assertEqual(count,6);self.assertEqual(len(registry),5)
        self.assertEqual(len(registry[2]['observations']),2)

class WorkflowTest(unittest.TestCase):
    def test_real_graph_mock_services(self):
        import importlib,os
        g=importlib.import_module('ollama_deep_researcher.graph')
        class FakeModel:
            calls=0
            def bind_tools(self, tools):return self
            def invoke(self,messages):
                self.calls+=1
                from types import SimpleNamespace
                return SimpleNamespace(content='Evidence [S1]',tool_calls=[{'args':{'query':'maintenance rag','follow_up_query':'maintenance evaluation'}}])
        for loops in [1,2]:
            model=FakeModel()
            with patch.dict(os.environ,{'LLM_PROVIDER':'openrouter','USE_TOOL_CALLING':'true','MAX_WEB_RESEARCH_LOOPS':str(loops),'SEARCH_API':'duckduckgo'}),patch.object(g,'get_llm',return_value=model),patch.object(g,'duckduckgo_search',return_value={'results':[{'url':'https://example.com/a','title':'A','content':'evidence','raw_content':'evidence'}]}):
                events=list(g.graph.stream({'research_topic':'maintenance'},stream_mode='updates'))
            nodes=[k for e in events for k in e]
            self.assertEqual(nodes.count('web_research'),loops)
            self.assertEqual(nodes.count('reflect_on_summary'),loops-1)
            self.assertEqual(model.calls,2*loops)
            self.assertEqual(events[-1]['finalize_summary']['citation_check']['status'],'passed')

if __name__=='__main__':unittest.main()
