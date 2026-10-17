"""逐层验证父进程身份；递归 children() 只提供候选，不能直接证明归属。"""
import math
import psutil


def _same(process, ref):
    return (process.pid == ref['pid'] and math.isfinite(ref['created'])
            # R/jsonlite 传输 epoch double 可能差约 0.24 微秒。
            and abs(process.create_time() - ref['created']) <= 1e-6)


def is_verified_descendant(candidate, owner, factory=psutil.Process, max_depth=64):
    """无法证明时返回 False；不结束进程，也不把未知归属解释为外部任务。"""
    try:
        if not _same(factory(owner['pid']), owner):
            return False
        leaf = dict(pid=candidate.pid, created=candidate.create_time())
        current = factory(leaf['pid'])
        if not _same(current, leaf) or current.pid == owner['pid']:
            return False
        edges, seen = [], set()
        for _ in range(max_depth):
            created = current.create_time()
            if current.pid in seen or not math.isfinite(created):
                return False
            seen.add(current.pid)
            parent_pid = current.ppid()
            if parent_pid <= 0 or parent_pid == current.pid:
                return False
            parent = factory(parent_pid)
            parent_created = parent.create_time()
            # 关键是每一条边，不能只把后代时间与最外层 R 进程比较。
            if not math.isfinite(parent_created) or parent_created > created:
                return False
            edges.append((dict(pid=current.pid, created=created),
                          dict(pid=parent.pid, created=parent_created)))
            if parent.pid == owner['pid']:
                if not _same(parent, owner):
                    return False
                # 重新读取整条链，拒绝枚举过程中退出、换父或被复用的 PID。
                for child_ref, parent_ref in edges:
                    child_now, parent_now = factory(child_ref['pid']), factory(parent_ref['pid'])
                    if (not _same(child_now, child_ref) or not _same(parent_now, parent_ref)
                            or child_now.ppid() != parent_ref['pid']):
                        return False
                return True
            current = parent
        return False
    except psutil.Error:
        return False


def verified_descendants(parent, factory=psutil.Process, names=None):
    """保留真实子孙，排除任何含陈旧父 PID、缺失或不可读祖先的候选。"""
    owner = dict(pid=parent.pid, created=parent.create_time())
    if not _same(factory(parent.pid), owner):
        raise RuntimeError('Owner identity changed')
    result=[]
    for child in parent.children(recursive=True):
        try:
            # 调度只需要 Mplus；避免对整个桌面/WebView 子树逐条查询。
            if names is not None and child.name().lower() not in names:
                continue
            if is_verified_descendant(child,owner,factory):
                result.append(child)
        except psutil.Error:
            continue
    if not _same(factory(parent.pid), owner):
        raise RuntimeError('Owner identity changed during enumeration')
    return result
