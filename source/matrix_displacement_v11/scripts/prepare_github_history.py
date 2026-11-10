"""Import archived source snapshots into an isolated Git repository, without changing originals."""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import subprocess
import os

project=Path(__file__).resolve().parents[3]
source=project/'source/matrix_displacement_v11'
repo=source/'outputs/github/MatrixDisplacement'
if repo.exists():
    raise SystemExit('Prepared repository already exists; inspect before rerunning.')
repo.mkdir(parents=True)
def git(*args):
    subprocess.run(['git',*args],cwd=repo,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
git('init','-b','main')
git('config','user.name','ZeyuWen17')
git('config','user.email','354438711+ZeyuWen17@users.noreply.github.com')
written=[]
excluded={'.git','.venv','__pycache__','.pytest_cache','outputs','build','dist'}
def put(name,data):
    p=repo/name
    if not p.resolve().is_relative_to(repo.resolve()): raise ValueError(name)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(data)
    written.append(p)
def snapshot(files,version):
    for p in written: p.unlink()
    written.clear()
    for name,data in files:
        if any(x in excluded for x in PurePosixPath(name).parts):continue
        if name.endswith(('.pyc','.zip','.spec')):continue
        put('source/matrix_displacement_v11/'+name,data)
    put('README.md',f'# MatrixDisplacement {version}\n\n结构力学矩阵位移法教学程序。\n\n源码位于 `source/matrix_displacement_v11`。安装该目录的 requirements-gui.txt 后，在该目录运行 `python -m matrix_displacement.gui`。\n\n历史源码从本地归档导入，提交日期是导入日期，不代表原始开发时间。原始 ZIP 和 Windows 程序见 GitHub Releases。V1.1 没有本地 Windows 归档。\n\n最新使用说明见源码目录的任务单；历史版本见各版本 README。\n'.encode())
    put('.gitignore',b'.venv/\n__pycache__/\n.pytest_cache/\noutputs/\nbuild/\ndist/\n*.pyc\n')
    git('add','-A')
    git('commit','-m',f'Import source snapshot {version}')
    git('tag',version)
for archive in sorted((project/'archive/releases').glob('*/*Full_Source.zip'),key=lambda p:tuple(map(int,p.parent.name[1:].split('.')))):
    with ZipFile(archive) as z:
        files=[]
        for name in z.namelist():
            path=PurePosixPath(name)
            if name.endswith('/'):continue
            if '..' in path.parts or path.is_absolute():raise ValueError(name)
            files.append(('/'.join(path.parts[1:]),z.read(name)))
    snapshot(files,archive.parent.name.lower())
files=[]
for directory,dirs,names in os.walk(source):
    dirs[:]=[d for d in dirs if d not in excluded]
    if Path(directory)==source/'reports/validation':dirs[:]=[]
    for name in names:
        p=Path(directory)/name
        files.append((p.relative_to(source).as_posix(),p.read_bytes()))
snapshot(files,'v1.1.5')
git('status','--porcelain')
print(repo)
