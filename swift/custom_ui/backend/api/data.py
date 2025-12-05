"""
数据管理 API 端点
提供数据上传、列表、删除、预览等功能
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import json
import csv
from pathlib import Path
from datetime import datetime

router = APIRouter()

# 数据存储目录（Docker volume 挂载点）
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 支持的文件格式
ALLOWED_EXTENSIONS = {".csv", ".jsonl", ".json", ".txt", ".tsv"}
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB

class DatasetInfo(BaseModel):
    """数据集信息（文件夹模式）"""
    name: str  # 文件夹名称
    path: str  # 相对路径
    is_directory: bool  # 是否为文件夹
    file_count: Optional[int] = None  # 文件夹内文件数量
    total_size: int  # 总大小（字节）
    size_mb: float  # 大小（MB）
    created_at: str
    modified_at: str

    # 兼容旧的文件模式
    filename: Optional[str] = None
    format: Optional[str] = None
    rows: Optional[int] = None

class UploadResponse(BaseModel):
    """上传响应"""
    filename: str
    filepath: str
    size_mb: float
    message: str

class DatasetPreview(BaseModel):
    """数据集预览"""
    filename: str
    format: str
    total_rows: int
    preview_rows: List[dict]
    columns: Optional[List[str]] = None

def get_directory_size(dirpath: Path) -> tuple[int, int]:
    """计算文件夹大小和文件数量"""
    total_size = 0
    file_count = 0
    try:
        for item in dirpath.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
    except Exception as e:
        print(f"Warning: Failed to calculate size for {dirpath}: {e}")
    return total_size, file_count

def get_dataset_info(path: Path) -> DatasetInfo:
    """获取数据集信息（支持文件夹和文件）"""
    stat = path.stat()

    if path.is_dir():
        # 文件夹模式
        total_size, file_count = get_directory_size(path)
        return DatasetInfo(
            name=path.name,
            path=str(path.relative_to(DATA_DIR)),
            is_directory=True,
            file_count=file_count,
            total_size=total_size,
            size_mb=round(total_size / (1024 * 1024), 2),
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat()
        )
    else:
        # 文件模式（兼容旧版本）
        file_size = stat.st_size
        rows = None
        if path.suffix in [".csv", ".jsonl", ".txt", ".tsv"]:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    rows = sum(1 for _ in f)
            except:
                pass

        return DatasetInfo(
            name=path.name,
            path=str(path.relative_to(DATA_DIR)),
            is_directory=False,
            file_count=1,
            total_size=file_size,
            size_mb=round(file_size / (1024 * 1024), 2),
            filename=path.name,
            format=path.suffix.lstrip('.'),
            rows=rows,
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat()
        )

@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)):
    """
    上传数据集文件

    支持的格式: CSV, JSONL, JSON, TXT, TSV
    最大文件大小: 1GB

    Args:
        file: 上传的文件

    Returns:
        UploadResponse: 上传结果
    """
    # 验证文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 {file_ext}。支持的格式: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 生成安全的文件名（防止路径遍历攻击）
    safe_filename = Path(file.filename).name
    filepath = DATA_DIR / safe_filename

    # 检查文件是否已存在
    if filepath.exists():
        raise HTTPException(
            status_code=409,
            detail=f"文件 {safe_filename} 已存在，请先删除或重命名"
        )

    # 保存文件
    try:
        with open(filepath, "wb") as buffer:
            file_size = 0
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # 删除部分上传的文件
                    buffer.close()
                    filepath.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件大小超过限制 ({MAX_FILE_SIZE / (1024**3)}GB)"
                    )
                buffer.write(chunk)

        return UploadResponse(
            filename=safe_filename,
            filepath=str(filepath.relative_to(DATA_DIR)),
            size_mb=round(file_size / (1024 * 1024), 2),
            message="文件上传成功"
        )

    except Exception as e:
        # 清理失败的上传
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.post("/upload-folder")
async def upload_folder(files: List[UploadFile] = File(...), folder_name: str = ""):
    """
    上传数据集文件夹（批量上传）

    前端需要将文件夹内所有文件一起上传，并指定文件夹名称

    Args:
        files: 文件列表
        folder_name: 文件夹名称

    Returns:
        dict: 上传结果
    """
    if not folder_name:
        raise HTTPException(status_code=400, detail="必须指定文件夹名称")

    # 创建文件夹
    folder_path = DATA_DIR / folder_name
    if folder_path.exists():
        raise HTTPException(status_code=409, detail=f"文件夹 {folder_name} 已存在")

    try:
        folder_path.mkdir(parents=True, exist_ok=False)

        total_size = 0
        uploaded_files = []

        for file in files:
            # 保存文件到文件夹
            safe_filename = Path(file.filename).name
            filepath = folder_path / safe_filename

            with open(filepath, "wb") as buffer:
                file_size = 0
                while chunk := await file.read(1024 * 1024):
                    file_size += len(chunk)
                    buffer.write(chunk)

            total_size += file_size
            uploaded_files.append(safe_filename)

        return {
            "folder_name": folder_name,
            "file_count": len(uploaded_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": uploaded_files,
            "message": f"成功上传文件夹 {folder_name}，共 {len(uploaded_files)} 个文件"
        }

    except Exception as e:
        # 清理失败的上传
        if folder_path.exists():
            shutil.rmtree(folder_path)
        raise HTTPException(status_code=500, detail=f"文件夹上传失败: {str(e)}")

@router.get("/list", response_model=List[DatasetInfo])
async def list_datasets(include_files: bool = False):
    """
    获取所有已上传的数据集列表（默认只返回文件夹）

    Args:
        include_files: 是否包含文件（默认 False，只返回文件夹）

    Returns:
        List[DatasetInfo]: 数据集信息列表
    """
    datasets = []

    for item in DATA_DIR.iterdir():
        # 默认只扫描文件夹
        if item.is_dir():
            try:
                datasets.append(get_dataset_info(item))
            except Exception as e:
                print(f"Warning: Failed to read directory {item}: {e}")
                continue
        # 可选：也包含单个文件（用于兼容旧数据）
        elif include_files and item.is_file() and item.suffix.lower() in ALLOWED_EXTENSIONS:
            try:
                datasets.append(get_dataset_info(item))
            except Exception as e:
                print(f"Warning: Failed to read file {item}: {e}")
                continue

    # 按修改时间倒序排序
    datasets.sort(key=lambda x: x.modified_at, reverse=True)

    return datasets

@router.get("/preview/{filename}", response_model=DatasetPreview)
async def preview_dataset(filename: str, rows: int = 10):
    """
    预览数据集内容

    Args:
        filename: 文件名
        rows: 预览行数（默认 10）

    Returns:
        DatasetPreview: 数据集预览信息
    """
    filepath = DATA_DIR / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    file_ext = filepath.suffix.lower()
    preview_data = []
    total_rows = 0
    columns = None

    try:
        if file_ext == ".csv":
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                for i, row in enumerate(reader):
                    if i < rows:
                        preview_data.append(row)
                    total_rows = i + 1

        elif file_ext == ".tsv":
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                columns = reader.fieldnames
                for i, row in enumerate(reader):
                    if i < rows:
                        preview_data.append(row)
                    total_rows = i + 1

        elif file_ext == ".jsonl":
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if line.strip():
                        data = json.loads(line)
                        if i < rows:
                            preview_data.append(data)
                        if i == 0 and isinstance(data, dict):
                            columns = list(data.keys())
                        total_rows = i + 1

        elif file_ext == ".json":
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    preview_data = data[:rows]
                    total_rows = len(data)
                    if data and isinstance(data[0], dict):
                        columns = list(data[0].keys())
                else:
                    preview_data = [data]
                    total_rows = 1

        elif file_ext == ".txt":
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i < rows:
                        preview_data.append({"text": line.strip()})
                    total_rows = i + 1
            columns = ["text"]

        else:
            raise HTTPException(status_code=400, detail="不支持预览此文件格式")

        return DatasetPreview(
            filename=filename,
            format=file_ext.lstrip('.'),
            total_rows=total_rows,
            preview_rows=preview_data,
            columns=columns
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON 格式错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")

@router.get("/download/{filename}")
async def download_dataset(filename: str):
    """
    下载数据集文件

    Args:
        filename: 文件名

    Returns:
        FileResponse: 文件下载响应
    """
    filepath = DATA_DIR / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

@router.delete("/delete/{filename}")
async def delete_dataset(filename: str):
    """
    删除数据集文件

    Args:
        filename: 文件名

    Returns:
        dict: 操作结果
    """
    filepath = DATA_DIR / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        filepath.unlink()
        return {"message": f"文件 {filename} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.get("/info/{name}", response_model=DatasetInfo)
async def get_dataset_info_endpoint(name: str):
    """
    获取数据集详细信息（支持文件夹和文件）

    Args:
        name: 文件夹名或文件名

    Returns:
        DatasetInfo: 数据集信息
    """
    path = DATA_DIR / name

    if not path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在")

    return get_dataset_info(path)
