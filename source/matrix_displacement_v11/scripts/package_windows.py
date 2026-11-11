"""Package an existing validated Windows onedir build, then test its extracted copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def package(version,root):
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Expected a three-part version')
    build=root/'outputs'/'dist'/('V'+version)/'MatrixDisplacement'
    exe=build/'MatrixDisplacement.exe'
    record=(build/'BUILD_VALIDATION.txt').read_text(encoding='utf-8-sig')
    assert f'V{version} -' in record, 'Build version mismatch'
    digest=sha256(exe)
    assert digest.upper() in record, 'EXE differs from validated build'
    with exe.open('rb') as stream:
        stream.seek(0x3c)
        offset=struct.unpack('<I',stream.read(4))[0]
        stream.seek(offset)
        assert stream.read(4)==b'PE\0\0'
        assert struct.unpack('<H',stream.read(2))[0]==0x8664, 'Expected Windows x64'
    assert (build/'_internal').is_dir()
    output=root/'outputs'/'releases'
    output.mkdir(parents=True,exist_ok=True)
    archive=output/f'MatrixDisplacement_V{version}_Windows.zip'
    instructions=f'''MatrixDisplacement V{version} — Windows x64 免安装版

1. 将整个 ZIP 解压到有写权限的文件夹。
2. 打开 MatrixDisplacement 文件夹，双击 MatrixDisplacement.exe。
3. 保留 _internal 文件夹及其全部内容，不要只复制 EXE。
4. 无需单独安装 Python。请勿直接在压缩包预览窗口运行 EXE。
5. 自动恢复在编辑停顿后写入草稿，重要修改请主动保存 JSON。

项目：https://github.com/ZeyuWen17/MatrixDisplacement
本版本说明：https://github.com/ZeyuWen17/MatrixDisplacement/releases/tag/v{version}
包内 BUILD_VALIDATION.txt 记录原构建校验。
本包经过解压后的隔离 PATH 离屏自检；不等同于另一台无 Python 电脑的真实界面验收。
'''
    files=sorted(p for p in build.rglob('*') if p.is_file())
    if not archive.exists():
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
            for path in files:
                bundle.write(path,Path('MatrixDisplacement')/path.relative_to(build))
            bundle.writestr('使用说明.txt',instructions.encode('utf-8-sig'))
    with tempfile.TemporaryDirectory(prefix=f'portable-{version}-',dir=output) as folder:
        with zipfile.ZipFile(archive) as bundle:
            expected={'MatrixDisplacement/'+p.relative_to(build).as_posix() for p in files}|{'使用说明.txt'}
            assert set(bundle.namelist())==expected, 'Archive contains unexpected files'
            assert bundle.testzip() is None
            bundle.extractall(folder)
        unpacked=Path(folder)/'MatrixDisplacement'
        for path in files:
            assert sha256(path)==sha256(unpacked/path.relative_to(build)), path
        env=os.environ.copy()
        for key in ('PYTHONHOME','PYTHONPATH'):
            env.pop(key,None)
        windows=next(value for key,value in env.items() if key.upper()=='SYSTEMROOT')
        env['PATH']=str(Path(windows)/'System32')+';'+windows
        env['QT_QPA_PLATFORM']='offscreen'
        env['QT_SCALE_FACTOR']='1'
        env['MATRIX_DISPLACEMENT_RECOVERY_DIR']=str(Path(folder)/'recovery')
        result=subprocess.run([str(unpacked/'MatrixDisplacement.exe'),'--self-test'],
                              cwd=folder,env=env,timeout=120,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0, f'Extracted self-test failed: {result.returncode}'
    zipped_hash=sha256(archive)
    checksum=archive.with_name(f'MatrixDisplacement_V{version}_SHA256.txt')
    checksum.write_text(zipped_hash+'  '+archive.name+'\n',encoding='utf-8')
    summary=dict(version=version,archive=archive.name,bytes=archive.stat().st_size,
                 sha256=zipped_hash,exe_sha256=digest,files=len(files),
                 extracted_files_verified=True,isolated_path_self_test='PASS',architecture='Windows x64')
    archive.with_suffix('.validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('versions',nargs='+')
    args=parser.parse_args()
    for version in args.versions:
        package(version,Path(__file__).resolve().parents[1])
