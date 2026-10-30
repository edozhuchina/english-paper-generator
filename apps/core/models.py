"""可复用的抽象模型基类：时间戳、软删除。"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """创建/更新时间。"""

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """默认过滤掉已软删除的记录。"""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_objects(self):
        """包含已删除记录的查询集。"""
        return super().get_queryset()

    def deleted(self):
        return super().get_queryset().filter(is_deleted=True)


class SoftDeleteModel(models.Model):
    """软删除基类：delete() 只打标记，hard_delete() 才真正删行。"""

    is_deleted = models.BooleanField("已删除", default=False, db_index=True)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        update_fields = ["is_deleted", "deleted_at"]
        if hasattr(self, "updated_at"):
            self.updated_at = timezone.now()
            update_fields.append("updated_at")
        self.save(update_fields=update_fields)
        return (1, {self._meta.label: 1})

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])
