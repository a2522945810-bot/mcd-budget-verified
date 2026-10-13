#!/usr/bin/env python3
"""Discover McDonald's official MCP tool schemas without invoking business tools.
Standard library only. Does not create orders, query coupons or save credentials.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = 'https://mcp.mcd.cn'
VERSIONS = {'2025-06-18', '2025-03-26'}
READ_TOOLS = {'query-nearby-stores', 'query-meals', 'query-meal-detail',
              'query-store-coupons', 'calculate-price', 'list-nutrition-foods'}
MAX_BYTES = 2 * 1024 * 1024


class ConnectionErrorSafe(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectionErrorSafe('服务发生重定向，已停止以避免转发凭证。')


def parse_response(response, expected_id):
    content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
    if content_type == 'application/json':
        raw = response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ConnectionErrorSafe('服务响应过大。')
        message = json.loads(raw)
        return extract_result(message, expected_id)
    if content_type == 'text/event-stream':
        total = 0; data=[]; started=time.monotonic()
        while time.monotonic()-started < 30:
            raw=response.readline(MAX_BYTES+1-total)
            if not raw: break
            total += len(raw)
            if total > MAX_BYTES: raise ConnectionErrorSafe('服务响应过大。')
            line=raw.decode('utf-8').rstrip('\r\n')
            if not line:
                if data:
                    message=json.loads('\n'.join(data));data=[]
                    if isinstance(message,dict) and message.get('id')==expected_id:
                        return extract_result(message,expected_id)
            elif line.startswith('data:'):
                data.append(line[5:].lstrip(' '))
        raise ConnectionErrorSafe('未收到匹配的MCP响应或响应超时。')
    raise ConnectionErrorSafe('服务返回了不支持的响应格式。')


def extract_result(message, expected_id):
    if not isinstance(message,dict) or message.get('jsonrpc')!='2.0' or message.get('id')!=expected_id:
        raise ConnectionErrorSafe('MCP响应编号或格式不匹配。')
    if 'error' in message:
        # Server error text can contain submitted credentials or private payloads.
        raise ConnectionErrorSafe('MCP服务拒绝请求；未输出原始错误内容。')
    result=message.get('result')
    if not isinstance(result,dict): raise ConnectionErrorSafe('MCP返回结果格式错误。')
    return result


class DiscoveryClient:
    def __init__(self, token, opener=None):
        if not token or any(ord(c)<33 or ord(c)>126 for c in token):
            raise ConnectionErrorSafe('凭证为空或包含非法字符。')
        self._token=token
        self._opener=opener or urllib.request.build_opener(NoRedirect())
        self._session=None;self._version=None;self._counter=0

    def request(self, method, params=None, notification=False):
        headers={'Authorization':'Bearer '+self._token,'Accept':'application/json, text/event-stream',
                 'Content-Type':'application/json'}
        if self._session:headers['Mcp-Session-Id']=self._session
        if self._version:headers['MCP-Protocol-Version']=self._version
        body={'jsonrpc':'2.0','method':method}
        if params is not None:body['params']=params
        if not notification:
            self._counter+=1;body['id']=self._counter
        req=urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),headers=headers,method='POST')
        try:
            with self._opener.open(req, timeout=15) as response:
                if notification:
                    if response.status!=202:raise ConnectionErrorSafe('初始化通知未被确认。')
                    return None
                result=parse_response(response,body['id'])
                if method=='initialize':
                    sid=response.headers.get('Mcp-Session-Id')
                    if sid and (len(sid)>4096 or any(ord(c)<33 or ord(c)>126 for c in sid)):
                        raise ConnectionErrorSafe('服务返回非法会话编号。')
                    self._session=sid
                return result
        except urllib.error.HTTPError as e:
            reason={401:'凭证无效或已过期，请在官网重新激活。',403:'请求未获授权。',
                    404:'服务或会话不可用，请重新运行连接。',429:'请求过于频繁，请稍后重试。'}
            raise ConnectionErrorSafe(reason.get(e.code,f'HTTP请求失败（{e.code}）。')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ConnectionErrorSafe('网络连接失败或超时，请检查网络与客户端。') from None

    def discover(self):
        result=self.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},
                          'clientInfo':{'name':'mcd-budget-verified-discovery','version':'0.1.0'}})
        if result.get('protocolVersion') not in VERSIONS:
            raise ConnectionErrorSafe('协商出的MCP协议版本尚不受本工具支持。')
        self._version=result['protocolVersion']
        if not isinstance(result.get('capabilities'),dict) or 'tools' not in result['capabilities']:
            raise ConnectionErrorSafe('服务未提供tools能力。')
        self.request('notifications/initialized',notification=True)
        tools=[];seen_cursors=set();cursor=None
        for _ in range(10):
            result=self.request('tools/list',{'cursor':cursor} if cursor else {})
            page=result.get('tools')
            if not isinstance(page,list):raise ConnectionErrorSafe('工具列表格式错误。')
            for tool in page:
                if not isinstance(tool,dict) or not isinstance(tool.get('name'),str) or not isinstance(tool.get('inputSchema'),dict):
                    raise ConnectionErrorSafe('工具定义不完整。')
                if tool['name'] in READ_TOOLS:
                    tools.append({k:tool[k] for k in ('name','inputSchema')})
            cursor=result.get('nextCursor')
            if not cursor:break
            if not isinstance(cursor,str) or cursor in seen_cursors:raise ConnectionErrorSafe('工具分页异常。')
            seen_cursors.add(cursor)
        else:raise ConnectionErrorSafe('工具分页超过上限。')
        names=[t['name'] for t in tools]
        if len(names)!=len(set(names)):raise ConnectionErrorSafe('服务返回重复工具定义。')
        return {'endpoint':ENDPOINT,'protocol_version':self._version,'business_calls_performed':0,
                'tools':tools,'missing_core_tools':sorted(READ_TOOLS-{'list-nutrition-foods'}-set(names))}

    def close(self):
        if self._session:
            req=urllib.request.Request(ENDPOINT,method='DELETE',headers={
                'Authorization':'Bearer '+self._token,'Mcp-Session-Id':self._session,
                'MCP-Protocol-Version':self._version or '2025-06-18'})
            try:
                with self._opener.open(req,timeout=5):pass
            except Exception:pass
        self._token='';self._session=None


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prompt-token',action='store_true',help='在当前终端隐藏输入Token')
    ap.add_argument('--output',help='可选：保存工具定义到本机私有文件，绝不保存Token')
    a=ap.parse_args(argv);client=None
    try:
        if a.prompt_token:
            if not sys.stdin.isatty():raise ConnectionErrorSafe('隐藏输入需要交互终端。')
            token=getpass.getpass('麦当劳MCP Token（仅本机使用，不回显）：')
        else:token=os.environ.get('MCD_MCP_TOKEN','')
        if not token:raise ConnectionErrorSafe('未设置凭证。请在自己电脑运行 --prompt-token；不要把Token发到聊天。')
        client=DiscoveryClient(token);manifest=client.discover()
        if a.output:
            path=Path(a.output)
            # Exclusive creation prevents accidentally replacing an existing file/symlink.
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
        print('连接成功，发现本项目可用工具：'+', '.join(t['name'] for t in manifest['tools']))
        print('未调用业务工具，未查询账户或创建订单。')
        if manifest['missing_core_tools']:print('缺少核心工具：'+', '.join(manifest['missing_core_tools']))
        return 0 if not manifest['missing_core_tools'] else 3
    except (ConnectionErrorSafe,ValueError,KeyError,OSError,EOFError):
        # Never emit unknown exceptions containing server responses or token values.
        exc=sys.exc_info()[1]
        print(str(exc) if isinstance(exc,ConnectionErrorSafe) else '连接或输出失败；未输出可能含敏感信息的原始错误。',file=sys.stderr)
        return 2
    finally:
        if client:client.close()


if __name__=='__main__':sys.exit(main())
