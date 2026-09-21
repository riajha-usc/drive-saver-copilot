"""Shared dependencies and error translation for the routers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from backend.api.store import Dataset, store
from backend.ml.predict import ModelNotTrained, load_bundle


def get_bundle():
    """The trained model, or a 503 telling the caller how to fix it."""
    try:
        return load_bundle()
    except ModelNotTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)) from exc


def get_dataset(dataset_id: str) -> Dataset:
    ds = store.get(dataset_id)
    if ds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no dataset {dataset_id!r}. Upload one at POST /datasets "
                   f"or use the seeded sample.")
    return ds


def get_asset_index(dataset_id: str, asset_id: str,
                    ds: Dataset = Depends(get_dataset)) -> tuple[Dataset, int]:
    index = ds.row_index(asset_id)
    if index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no asset {asset_id!r} in dataset {dataset_id!r} "
                   f"({len(ds.frame)} assets, ids run VFD-0000 upward)")
    return ds, index
