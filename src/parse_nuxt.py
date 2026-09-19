import json
import re
from pathlib import Path


def replace_identifiers(js_text, mapping):
    result = []
    i = 0
    n = len(js_text)
    in_string = False
    quote_char = ''
    while i < n:
        ch = js_text[i]
        if in_string:
            result.append(ch)
            if ch == '\\':
                if i + 1 < n:
                    result.append(js_text[i + 1])
                    i += 2
                    continue
            elif ch == quote_char:
                in_string = False
            i += 1
        else:
            if ch in ('"', '\''):
                in_string = True
                quote_char = ch
                result.append(ch)
                i += 1
            elif ch.isalpha() or ch == '_' or ch == '$':
                start = i
                i += 1
                while i < n and (js_text[i].isalnum() or js_text[i] in ('_', '$')):
                    i += 1
                identifier = js_text[start:i]
                if identifier in mapping:
                    result.append(json.dumps(mapping[identifier]))
                else:
                    result.append(identifier)
            else:
                result.append(ch)
                i += 1
    return ''.join(result)


def js_object_to_json(js_text):
    js_text = re.sub(r'(?<=\{|,)(\s*)([A-Za-z0-9_]+)\s*:', lambda m: f'{m.group(1)}"{m.group(2)}":', js_text)
    js_text = js_text.replace("'", '"')
    # 替换JavaScript特殊值
    js_text = js_text.replace('undefined', 'null')
    js_text = re.sub(r'\bvoid\s+0\b', 'null', js_text)  # 替换 void 0
    js_text = re.sub(r'\bvoid\s+1\b', 'null', js_text)  # 替换 void 1
    js_text = re.sub(r'\bvoid\s+\(0\)\b', 'null', js_text)  # 替换 void(0)
    js_text = js_text.replace('NaN', 'null')
    js_text = re.sub(r':(-?)\.(\d+)', lambda m: f':{m.group(1)}0.{m.group(2)}', js_text)
    # 移除尾随逗号
    js_text = re.sub(r',\s*}', '}', js_text)
    js_text = re.sub(r',\s*]', ']', js_text)
    return js_text


def parse_nuxt_from_text(text):
    # 尝试多种正则表达式模式匹配
    patterns = [
        r"window\.__NUXT__=\(function\(([^)]*)\)\{return (\{.*?\})\}\((.*)\);",
        r"window\.__NUXT__\s*=\s*\(function\(([^)]*)\)\{return (\{.*?\})\}\((.*)\);",
        r"__NUXT__\s*=\s*\(function\(([^)]*)\)\{return (\{.*?\})\}\((.*)\);",
        r"window\.__NUXT__\s*=\s*(\{.*?\});",
    ]
    
    match = None
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            break
    
    if not match:
        # 尝试直接查找JSON对象
        json_match = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});", text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1)
                # 清理可能的JavaScript语法
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                return json.loads(json_str)
            except:
                pass
        raise ValueError('window.__NUXT__ payload not found in HTML')

    # 如果匹配到的是简化模式（直接JSON）
    if len(match.groups()) == 1:
        try:
            json_str = match.group(1)
            json_str = json_str.replace("'", '"')
            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
            return json.loads(json_str)
        except Exception as e:
            raise ValueError(f'Failed to parse JSON directly: {e}')

    params = [p.strip() for p in match.group(1).split(',') if p.strip()]
    body = match.group(2)
    args_str = match.group(3)

    args_clean = args_str.strip()
    if args_clean.startswith('(') and args_clean.endswith(')'):
        args_clean = args_clean[1:-1]
    args_clean = args_clean.strip()
    while args_clean.endswith(')'):
        args_clean = args_clean[:-1].rstrip()

    for old, new in (('Array(0)', '[]'), ('!0', 'true'), ('!1', 'false')):
        args_clean = args_clean.replace(old, new)

    # 改进JSON解析，添加错误处理
    try:
        # 尝试直接解析
        mapping_values = json.loads('[' + args_clean + ']')
    except json.JSONDecodeError as e:
        # 如果失败，尝试清理更多JavaScript语法
        args_clean = re.sub(r'undefined', 'null', args_clean)
        args_clean = re.sub(r'NaN', 'null', args_clean)
        args_clean = re.sub(r':(-?)\.(\d+)', lambda m: f':{m.group(1)}0.{m.group(2)}', args_clean)
        
        # 尝试修复常见的JSON问题
        try:
            mapping_values = json.loads('[' + args_clean + ']')
        except json.JSONDecodeError:
            # 如果还是失败，尝试逐个解析参数
            try:
                # 分割参数并逐个解析
                param_parts = []
                depth = 0
                current = ""
                for char in args_clean:
                    if char in '([{':
                        depth += 1
                        current += char
                    elif char in ')]}':
                        depth -= 1
                        current += char
                    elif char == ',' and depth == 0:
                        if current.strip():
                            param_parts.append(current.strip())
                        current = ""
                    else:
                        current += char
                if current.strip():
                    param_parts.append(current.strip())
                
                mapping_values = []
                for part in param_parts:
                    try:
                        # 清理每个部分
                        part = part.replace('undefined', 'null').replace('NaN', 'null')
                        part = re.sub(r':(-?)\.(\d+)', lambda m: f':{m.group(1)}0.{m.group(2)}', part)
                        mapping_values.append(json.loads(part))
                    except:
                        mapping_values.append(None)
            except Exception as e2:
                raise ValueError(f'Failed to parse arguments: {e}, secondary error: {e2}, args_clean: {args_clean[:200]}')

    mapping = {name: value for name, value in zip(params, mapping_values)}

    body_replaced = replace_identifiers(body, mapping).replace('Array(0)', '[]')
    body_json = js_object_to_json(body_replaced)
    
    try:
        return json.loads(body_json)
    except json.JSONDecodeError as e:
        # 如果最终解析失败，尝试修复更多常见问题
        # 再次清理JavaScript语法
        body_json = body_json.replace('undefined', 'null')
        body_json = re.sub(r'\bvoid\s+0\b', 'null', body_json)
        body_json = re.sub(r'\bvoid\s+1\b', 'null', body_json)
        body_json = re.sub(r'\bvoid\s*\(0\)\b', 'null', body_json)
        body_json = body_json.replace('NaN', 'null')
        body_json = re.sub(r',\s*}', '}', body_json)  # 移除尾随逗号
        body_json = re.sub(r',\s*]', ']', body_json)
        
        # 尝试修复未加引号的键
        body_json = re.sub(r'(\{|,)\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*:', r'\1"\2":', body_json)
        
        try:
            return json.loads(body_json)
        except json.JSONDecodeError as e2:
            # 如果还是失败，尝试更激进的修复
            try:
                # 尝试使用json5或更宽松的解析
                # 修复单引号字符串
                body_json = re.sub(r"'([^']*)'", r'"\1"', body_json)
                # 修复未加引号的键（更激进）
                body_json = re.sub(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*:', r'\1"\2":', body_json)
                return json.loads(body_json)
            except json.JSONDecodeError:
                # 最后尝试：找到错误位置并修复
                error_pos = e2.pos if hasattr(e2, 'pos') else None
                if error_pos and error_pos < len(body_json):
                    # 在错误位置前后显示更多上下文
                    start = max(0, error_pos - 100)
                    end = min(len(body_json), error_pos + 100)
                    context = body_json[start:end]
                    raise ValueError(f'Failed to parse final JSON: {e}, after fix: {e2}, error at position {error_pos}, context: ...{context}...')
                else:
                    raise ValueError(f'Failed to parse final JSON: {e}, after fix: {e2}, body_json preview: {body_json[:500]}')


def parse_nuxt_from_file(path):
    text = Path(path).read_text(encoding='utf-8')
    return parse_nuxt_from_text(text)
