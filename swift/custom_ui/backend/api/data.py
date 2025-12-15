"""
数据管理 API 端点
提供数据上传、列表、删除、预览等功能
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
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

# Web 上传支持的文件格式（文本和结构化数据）
# 注意：大文件（图片、音频、视频）建议通过 Docker volume 或文件夹上传
ALLOWED_EXTENSIONS = {
    # 文本数据格式
    ".csv", ".jsonl", ".json", ".txt", ".tsv",
    # Parquet/Arrow 格式（HuggingFace 默认格式）
    ".parquet", ".pq", ".arrow",
}
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

class FolderPreview(BaseModel):
    """文件夹预览"""
    folder_name: str
    files: List[dict]  # 文件列表：[{name, size, type, modified_at}]
    total_files: int
    total_size_mb: float

def get_directory_size(dirpath: Path) -> tuple[int, int]:
    """计算文件夹大小和文件数量"""
    import traceback
    total_size = 0
    file_count = 0
    try:
        for item in dirpath.rglob('*'):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                    file_count += 1
                except PermissionError as pe:
                    print(f"Permission denied reading file {item}: {pe}")
                except Exception as e:
                    print(f"Error reading file {item}: {e}")
    except PermissionError as pe:
        print(f"Permission denied accessing directory {dirpath}: {pe}")
        print(traceback.format_exc())
    except Exception as e:
        print(f"Error calculating size for {dirpath}: {e}")
        print(traceback.format_exc())
    return total_size, file_count

def get_dataset_info(path: Path) -> DatasetInfo:
    """获取数据集信息（支持文件夹和文件）"""
    import traceback
    try:
        stat = path.stat()
        # 打印文件所有者信息（用于调试）
        try:
            import pwd
            owner_info = pwd.getpwuid(stat.st_uid)
            print(f"Path {path} owner: {owner_info.pw_name} (uid: {stat.st_uid})")
            current_uid = os.getuid() if hasattr(os, 'getuid') else -1
            if current_uid >= 0:
                current_user = pwd.getpwuid(current_uid)
                print(f"Current user: {current_user.pw_name} (uid: {current_uid})")
        except:
            pass  # 忽略无法获取用户信息的情况
    except PermissionError as pe:
        print(f"Permission denied reading stat for {path}: {pe}")
        raise
    except Exception as e:
        print(f"Error reading stat for {path}: {e}")
        print(traceback.format_exc())
        raise

    if path.is_dir():
        # 文件夹模式
        print(f"Processing directory: {path}")
        total_size, file_count = get_directory_size(path)
        print(f"Directory {path} - Size: {total_size} bytes, Files: {file_count}")
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

        # 设置文件权限为 644 (-rw-r--r--)，确保所有用户都能读取
        try:
            os.chmod(filepath, 0o644)
            print(f"Set file permissions to 644 for {filepath}")
        except Exception as e:
            print(f"Warning: Failed to set file permissions: {e}")

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
async def upload_folder(
    files: List[UploadFile] = File(...),
    folder_name: str = Form(...)
):
    """
    上传数据集文件夹（批量上传）

    前端需要将文件夹内所有文件一起上传，并指定文件夹名称

    Args:
        files: 文件列表
        folder_name: 文件夹名称（通过 Form 字段传递）

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

        # 设置文件夹权限为 755 (drwxr-xr-x)，确保所有用户都能读取
        try:
            os.chmod(folder_path, 0o755)
            print(f"Set folder permissions to 755 for {folder_path}")
        except Exception as e:
            print(f"Warning: Failed to set folder permissions: {e}")

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

            # 设置文件权限为 644 (-rw-r--r--)
            try:
                os.chmod(filepath, 0o644)
            except Exception as e:
                print(f"Warning: Failed to set file permissions for {filepath}: {e}")

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
    import traceback
    datasets = []

    print(f"=== Listing datasets from {DATA_DIR} ===")
    print(f"Include files: {include_files}")

    try:
        items = list(DATA_DIR.iterdir())
        print(f"Found {len(items)} items in {DATA_DIR}")
    except PermissionError as pe:
        print(f"Permission denied listing {DATA_DIR}: {pe}")
        raise HTTPException(status_code=500, detail=f"Permission denied: {pe}")
    except Exception as e:
        print(f"Error listing {DATA_DIR}: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error listing directory: {e}")

    for item in items:
        print(f"Processing item: {item} (is_dir: {item.is_dir()}, is_file: {item.is_file()})")

        # 默认只扫描文件夹
        if item.is_dir():
            try:
                info = get_dataset_info(item)
                datasets.append(info)
                print(f"✓ Successfully added directory: {item.name}")
            except PermissionError as pe:
                print(f"✗ Permission denied for directory {item}: {pe}")
                print(traceback.format_exc())
                continue
            except Exception as e:
                print(f"✗ Failed to read directory {item}: {e}")
                print(traceback.format_exc())
                continue
        # 可选：也包含单个文件（用于兼容旧数据）
        elif include_files and item.is_file() and item.suffix.lower() in ALLOWED_EXTENSIONS:
            try:
                info = get_dataset_info(item)
                datasets.append(info)
                print(f"✓ Successfully added file: {item.name}")
            except Exception as e:
                print(f"✗ Failed to read file {item}: {e}")
                print(traceback.format_exc())
                continue

    # 按修改时间倒序排序
    datasets.sort(key=lambda x: x.modified_at, reverse=True)

    print(f"=== Returning {len(datasets)} datasets ===")
    return datasets

@router.get("/preview-folder/{folder_name}")
async def preview_folder(folder_name: str):
    """
    预览文件夹内容（文件列表）

    Args:
        folder_name: 文件夹名称

    Returns:
        FolderPreview: 文件夹预览信息
    """
    folder_path = DATA_DIR / folder_name

    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="文件夹不存在")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="不是文件夹")

    try:
        files = []
        total_size = 0

        for item in folder_path.iterdir():
            if item.is_file():
                stat = item.stat()
                file_size = stat.st_size
                total_size += file_size

                files.append({
                    "name": item.name,
                    "size": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "type": item.suffix.lstrip('.') or 'file',
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # 按文件名排序
        files.sort(key=lambda x: x['name'])

        return {
            "folder_name": folder_name,
            "files": files,
            "total_files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")

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

        elif file_ext in [".parquet", ".pq"]:
            # Parquet 格式支持（HuggingFace 默认格式）
            try:
                import pandas as pd
                df = pd.read_parquet(filepath)
                total_rows = len(df)
                columns = df.columns.tolist()
                preview_data = df.head(rows).to_dict('records')
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="预览 Parquet 文件需要安装 pandas 和 pyarrow: pip install pandas pyarrow"
                )

        elif file_ext == ".arrow":
            # Arrow 格式支持
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
                table = pq.read_table(filepath)
                df = table.to_pandas()
                total_rows = len(df)
                columns = df.columns.tolist()
                preview_data = df.head(rows).to_dict('records')
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="预览 Arrow 文件需要安装 pyarrow: pip install pyarrow"
                )

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

@router.delete("/delete/{name}")
async def delete_dataset(name: str):
    """
    删除数据集（支持文件和文件夹递归删除）

    Args:
        name: 文件名或文件夹名

    Returns:
        dict: 操作结果
    """
    path = DATA_DIR / name

    if not path.exists():
        raise HTTPException(status_code=404, detail="数据集不存在")

    try:
        if path.is_dir():
            # 递归删除文件夹
            shutil.rmtree(path)
            return {"message": f"文件夹 {name} 及其所有内容已删除"}
        else:
            # 删除单个文件
            path.unlink()
            return {"message": f"文件 {name} 已删除"}
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


# ============ 数据转换 API（标注数据 → HuggingFace Datasets） ============

class ConvertRequest(BaseModel):
    """数据转换请求"""
    project_name: str  # 标注项目文件夹名称
    output_format: str = "parquet"  # 输出格式: parquet 或 jsonl
    shard_size_mb: int = 100  # Parquet 分片大小（MB）
    include_overlays: bool = True  # 是否使用带标注框的 overlay 图片
    output_name: Optional[str] = None  # 输出文件夹名称（默认为 {project_name}_converted）


class ConvertResponse(BaseModel):
    """数据转换响应"""
    status: str
    output_folder: str  # 输出文件夹名称
    output_files: List[str]  # 生成的文件列表
    summary: dict  # 统计信息


class ValidationResponse(BaseModel):
    """项目验证响应"""
    valid: bool
    project_name: Optional[str] = None
    instruction_count: Optional[int] = None
    has_overlays: Optional[bool] = None
    structure: Optional[dict] = None
    error: Optional[str] = None


@router.post("/validate-annotation-project", response_model=ValidationResponse)
async def validate_annotation_project_endpoint(project_name: str):
    """
    验证标注项目结构

    Args:
        project_name: 标注项目文件夹名称

    Returns:
        ValidationResponse: 验证结果
    """
    from services.dataset_converter_service import validate_annotation_project

    try:
        result = validate_annotation_project(project_name)
        return ValidationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@router.post("/convert", response_model=ConvertResponse)
async def convert_annotation_dataset(request: ConvertRequest):
    """
    转换标注数据集为 HuggingFace Datasets 格式

    Args:
        request: 转换请求参数

    Returns:
        ConvertResponse: 转换结果
    """
    from services.dataset_converter_service import DatasetConverter

    try:
        # 初始化转换器
        converter = DatasetConverter(request.project_name)

        # 转换所有数据
        results = converter.convert_all(use_overlay=request.include_overlays)

        if not results:
            raise HTTPException(status_code=400, detail="没有成功转换的数据")

        # 确定输出目录
        output_name = request.output_name or f"{request.project_name}_converted"
        output_dir = DATA_DIR / output_name

        # 如果输出目录已存在，抛出错误
        if output_dir.exists():
            raise HTTPException(
                status_code=409,
                detail=f"输出文件夹 {output_name} 已存在，请先删除或选择其他名称"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存数据
        output_files = []

        if request.output_format == "parquet":
            if request.shard_size_mb > 0:
                # 分片保存
                output_files = converter.save_to_parquet_sharded(
                    results,
                    output_dir=str(output_dir),
                    output_prefix="train",
                    max_shard_size_mb=request.shard_size_mb,
                )
            else:
                # 单文件保存
                output_file = "train.parquet"
                converter.save_to_parquet(results, str(output_dir / output_file))
                output_files = [output_file]

        elif request.output_format == "jsonl":
            output_file = "train.jsonl"
            converter.save_to_jsonl(results, str(output_dir / output_file))
            output_files = [output_file]
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的输出格式: {request.output_format}"
            )

        # 获取统计信息
        stats = converter.get_statistics(results)

        return ConvertResponse(
            status="success",
            output_folder=output_name,
            output_files=output_files,
            summary=stats,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")


@router.get("/convert-formats")
async def get_convert_formats():
    """获取支持的转换格式"""
    return {
        "formats": [
            {
                "name": "parquet",
                "description": "Apache Parquet 格式，HuggingFace 推荐",
                "supports_sharding": True,
            },
            {
                "name": "jsonl",
                "description": "JSON Lines 格式，用于调试",
                "supports_sharding": False,
            },
        ],
        "media_types": [
            "image (jpg, png)",
            "pdf",
            "video (mp4)"
        ]
    }
