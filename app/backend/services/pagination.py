"""Helper page_info murni Python — dipakai bersama list Customer (TASK-C) dan
list Contract (TASK-D), pola paginasi yang SAMA persis di 2 tempat itu."""
import math

from domain.models import PageInfo


def build_page_info(total_count: int, page: int, page_size: int, returned_count: int) -> PageInfo:
    if total_count <= 0 or returned_count <= 0:
        return PageInfo(showing_from=0, showing_to=0, total_count=total_count, total_pages=max(1, math.ceil(total_count / page_size)))

    showing_from = (page - 1) * page_size + 1
    showing_to = showing_from + returned_count - 1
    total_pages = max(1, math.ceil(total_count / page_size))
    return PageInfo(showing_from=showing_from, showing_to=showing_to, total_count=total_count, total_pages=total_pages)
