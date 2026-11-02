from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.bank.models import Question
from apps.catalog.models import QuestionType, Tag


class QuestionListView(ListView):
    """题库列表：按题型 / 年级 / 难度 / 标签 / 关键词过滤。"""

    model = Question
    template_name = "bank/question_list.html"
    context_object_name = "questions"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Question.objects.select_related("question_type", "passage")
            .prefetch_related("tags")
            .order_by("-id")
        )
        params = self.request.GET

        type_code = params.get("type")
        if type_code:
            queryset = queryset.filter(question_type__code=type_code)

        group = params.get("group")
        if group:
            queryset = queryset.filter(question_type__group=group)

        grade = params.get("grade")
        if grade:
            queryset = queryset.filter(grade=grade)

        difficulty = params.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)

        tag = params.get("tag")
        if tag:
            queryset = queryset.filter(tags__id=tag)

        keyword = params.get("q")
        if keyword:
            queryset = queryset.filter(
                Q(stem__icontains=keyword)
                | Q(answer_text__icontains=keyword)
                | Q(explanation__icontains=keyword)
                | Q(code__icontains=keyword)
                | Q(passage__body__icontains=keyword)
            )

        status = params.get("status")
        if status:
            queryset = queryset.filter(review_status=status)
        else:
            queryset = queryset.filter(review_status="approved")

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context["types"] = QuestionType.objects.filter(is_active=True).order_by("group", "sort_order")
        context["tags"] = Tag.objects.all().order_by("category", "sort_order")
        context["total_count"] = Question.objects.filter(review_status="approved").count()
        context["request_params"] = params
        context["current_type"] = params.get("type", "")
        context["current_group"] = params.get("group", "")
        context["current_grade"] = params.get("grade", "")
        context["current_difficulty"] = params.get("difficulty", "")
        context["current_tag"] = params.get("tag", "")
        context["current_status"] = params.get("status", "")
        context["keyword"] = params.get("q", "")
        context["type_count"] = dict(
            Question.objects.filter(review_status="approved")
            .values_list("question_type__code")
            .annotate(count=Count("id"))
        )
        return context


class QuestionDetailView(DetailView):
    model = Question
    template_name = "bank/question_detail.html"
    context_object_name = "question"

    def get_queryset(self):
        return Question.objects.select_related("question_type", "passage", "audio", "stem_image")


class QuestionFormMixin:
    model = Question
    template_name = "bank/question_form.html"
    fields = [
        "question_type",
        "grade",
        "term",
        "difficulty",
        "code",
        "stem",
        "content",
        "answer",
        "explanation",
        "suggested_score",
        "options_layout",
        "expected_word_count",
        "review_status",
        "tags",
    ]

    def get_success_url(self):
        return reverse_lazy("bank:question-detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = QuestionType.objects.filter(is_active=True).order_by("group", "sort_order")
        return context


class QuestionCreateView(QuestionFormMixin, CreateView):
    pass


class QuestionUpdateView(QuestionFormMixin, UpdateView):
    pass


class QuestionDeleteView(View):
    """软删除（保留原题，可在后台恢复）。"""

    def post(self, request, pk, *args, **kwargs):
        question = Question.objects.filter(pk=pk).first()
        if question is None:
            return JsonResponse({"ok": False, "error": "题目不存在"}, status=404)
        question.delete()
        # next 来自表单，必须校验：否则 /bank/1/delete/ 可以被做成跳转到任意外站的中转页
        next_url = request.POST.get("next") or ""
        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = "/bank/"
        return HttpResponseRedirect(next_url)
