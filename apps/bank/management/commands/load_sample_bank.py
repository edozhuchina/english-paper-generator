"""加载内置样例题库，用于在没有真实题库时跑通「录入 → 组卷 → 导出」全流程。

用法：
    .venv\\Scripts\\python manage.py load_sample_bank            # 加载全部年级
    .venv\\Scripts\\python manage.py load_sample_bank --grade 5  # 只加载五年级
    .venv\\Scripts\\python manage.py load_sample_bank --clear    # 先清空样例题再加载
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bank.models import Passage, Question
from apps.catalog.models import QuestionType, Tag

GRADES = [3, 4, 5, 6]

# ============================================================ 听力 —— 听音选图/选词

LISTENING_CHOICE = {
    3: [
        ("听录音，选出你听到的单词。", ["pen", "pencil", "panda"], "B", ["话题:学习用品"]),
        ("听录音，选出你听到的单词。", ["cat", "cap", "car"], "C", ["话题:动物朋友"]),
        ("听录音，选出你听到的句子。", ["I'm six.", "I'm fine.", "I'm Sarah."], "A", ["语法:be 动词"]),
        ("听录音，选出与内容相符的图片。", ["a red apple", "a green pear", "a yellow banana"], "A", ["话题:食物饮料"]),
    ],
    4: [
        ("听录音，选出你听到的单词。", ["bedroom", "bathroom", "classroom"], "B", ["话题:房间家居"]),
        ("听录音，选出你听到的句子。", ["It's on the desk.", "It's in the bag.", "It's under the bed."], "C", ["语法:方位介词"]),
        ("听录音，选出正确的应答句。", ["Nice to meet you, too.", "You're welcome.", "I'm fine, thanks."], "A", ["话题:学校生活"]),
        ("听录音，选出你听到的单词。", ["eleven", "seven", "seventeen"], "A", ["话题:数字数量"]),
    ],
    5: [
        ("听录音，选出你听到的单词。", ["Wednesday", "Tuesday", "Thursday"], "C", ["话题:日程作息"]),
        ("听录音，选出正确的应答句。", ["He's a doctor.", "She's tall.", "He likes apples."], "A", ["话题:职业理想"]),
        ("听录音，选出你听到的句子。", ["I go to school by bus.", "I get up at six.", "I do homework at night."], "B", ["语法:一般现在时"]),
        ("听录音，选出与内容相符的图片。", ["making a snowman", "flying a kite", "riding a bike"], "B", ["话题:天气季节"]),
    ],
    6: [
        ("听录音，选出你听到的单词。", ["scientist", "secretary", "soldier"], "A", ["话题:职业理想"]),
        ("听录音，选出正确的应答句。", ["It was great!", "It's sunny.", "Yes, I did."], "C", ["语法:一般过去时"]),
        ("听录音，选出你听到的句子。", ["I went to the zoo.", "I'm going to swim.", "I have a cold."], "A", ["语法:一般过去时"]),
        ("听录音，选出与内容相符的图片。", ["turn left", "go straight", "turn right"], "B", ["话题:交通工具"]),
    ],
}

# ============================================================ 听力 —— 听句排序

LISTENING_ORDER = {
    3: [
        (["Nice to meet you.", "My name is Mike.", "Good morning!"], [3, 2, 1], ["话题:学校生活"]),
        (["It's a dog.", "Look! What's that?", "Wow, it's lovely."], [2, 1, 3], ["话题:动物朋友"]),
    ],
    4: [
        (["It's on the second floor.", "Excuse me, where is the library?", "Thank you very much."], [2, 1, 3], ["话题:学校生活"]),
        (["I get up at six thirty.", "Then I have breakfast.", "I go to school at seven."], [1, 2, 3], ["话题:日程作息"]),
    ],
    5: [
        (["How do you go to school?", "I go by bike.", "That's good exercise."], [1, 2, 3], ["话题:交通工具"]),
        (["What did you do yesterday?", "I visited my grandparents.", "Did you have a good time?"], [2, 1, 3], ["语法:一般过去时"]),
    ],
    6: [
        (["What are you going to do?", "I'm going to see a film.", "Sounds great!"], [1, 2, 3], ["语法:一般将来时"]),
        (["I have a fever.", "What's wrong with you?", "You should see a doctor."], [2, 1, 3], ["话题:看病就医"]),
    ],
}

# ============================================================ 听力/阅读 —— 判断正误

PASSAGE_JUDGE = {
    3: [
        {"title": "听短文：My Family", "kind": "listening_script", "type": "listening_judge",
         "body": "Hello! I'm Amy. I'm eight. This is my father. He's a teacher. This is my mother. She's a nurse. I love my family.",
         "statements": [("Amy is eight.", True), ("Her father is a doctor.", False), ("Her mother is a nurse.", True)]},
    ],
    4: [
        {"title": "听短文：Our School", "kind": "listening_script", "type": "listening_judge",
         "body": "Our school is big. There are twenty classrooms. The library is on the second floor. We have a big playground.",
         "statements": [("The school is small.", False), ("The library is on the second floor.", True), ("There is a big playground.", True)]},
    ],
    5: [
        {"title": "阅读短文：My Weekend", "kind": "reading", "type": "reading_judge",
         "body": "I had a busy weekend. On Saturday morning I did my homework. In the afternoon I played football with my friends. On Sunday I visited my grandparents and had dinner with them.",
         "statements": [("I watched TV on Saturday morning.", False), ("I played football with my friends.", True), ("I had dinner with my grandparents.", True)]},
    ],
    6: [
        {"title": "阅读短文：A Trip to Beijing", "kind": "reading", "type": "reading_judge",
         "body": "Last summer I went to Beijing with my parents. We visited the Great Wall and took many photos. We also ate Beijing duck. It was delicious. We came back by train.",
         "statements": [("I went to Beijing with my friends.", False), ("They ate Beijing duck.", True), ("They came back by train.", True)]},
    ],
}

# ============================================================ 单项选择

SINGLE_CHOICE = {
    3: [
        {"stem": "This ______ my mother.", "options": ["am", "is", "are"], "answer": "B",
         "explanation": "this 表单数，be 动词用 is。", "tags": ["be 动词"]},
        {"stem": "I ______ a student.", "options": ["am", "is", "are"], "answer": "A",
         "explanation": "I 后面用 am。", "tags": ["be 动词"]},
        {"stem": "— ______ is it? — It's a cat.", "options": ["What", "Who", "Where"], "answer": "A",
         "explanation": "问事物用 What。", "tags": ["特殊疑问句"]},
        {"stem": "I have ______ apple.", "options": ["a", "an", "the"], "answer": "B",
         "explanation": "apple 以元音音素开头，用 an。", "tags": ["名词单复数"]},
    ],
    4: [
        {"stem": "There ______ two books on the desk.", "options": ["is", "are", "am"], "answer": "B",
         "explanation": "two books 是复数，用 are。", "tags": ["There be 句型"]},
        {"stem": "The cat is ______ the chair.", "options": ["on", "in", "under"], "answer": "C",
         "explanation": "under 表示在……下面。", "tags": ["方位介词"]},
        {"stem": "My father ______ a car.", "options": ["have", "has", "having"], "answer": "B",
         "explanation": "第三人称单数用 has。", "tags": ["第三人称单数"]},
        {"stem": "I get up ______ six o'clock.", "options": ["in", "on", "at"], "answer": "C",
         "explanation": "具体时间点用 at。", "tags": ["时间表达"]},
    ],
    5: [
        {"stem": "She ______ to school by bike every day.", "options": ["go", "goes", "going"], "answer": "B",
         "explanation": "every day 表习惯，一般现在时，主语三单加 -es。", "tags": ["一般现在时", "第三人称单数"]},
        {"stem": "Listen! The birds ______ in the tree.", "options": ["sing", "sings", "are singing"], "answer": "C",
         "explanation": "Listen! 提示动作正在发生，用现在进行时。", "tags": ["现在进行时"]},
        {"stem": "Tom is ______ than Jim.", "options": ["tall", "taller", "tallest"], "answer": "B",
         "explanation": "than 前用比较级。", "tags": ["形容词比较级"]},
        {"stem": "It was sunny yesterday, ______ we went to the park.", "options": ["but", "so", "or"], "answer": "B",
         "explanation": "因果关系用 so。", "tags": []},
    ],
    6: [
        {"stem": "I ______ my homework yesterday evening.", "options": ["do", "did", "does"], "answer": "B",
         "explanation": "yesterday evening 用一般过去时，do 的过去式是 did。", "tags": ["一般过去时"]},
        {"stem": "We ______ to the zoo next Sunday.", "options": ["go", "went", "will go"], "answer": "C",
         "explanation": "next Sunday 表将来，用 will go。", "tags": ["一般将来时"]},
        {"stem": "There isn't ______ milk in the fridge.", "options": ["some", "any", "a"], "answer": "B",
         "explanation": "否定句中用 any。", "tags": ["不可数名词"]},
        {"stem": "The second month of the year is ______.", "options": ["January", "February", "March"], "answer": "B",
         "explanation": "一年的第二个月是 February。", "tags": ["序数词"]},
    ],
}

# ============================================================ 选词填空

BANKED_FILL = {
    3: [
        {"stem": "I have a new ______. It's red.", "bank": ["pen", "blue", "five"], "answer": ["pen"], "tags": ["学习用品"]},
        {"stem": "This is my ______. She is a nurse.", "bank": ["mother", "teacher", "dog"], "answer": ["mother"], "tags": ["家庭成员"]},
    ],
    4: [
        {"stem": "The library is on the ______ floor.", "bank": ["second", "two", "twice"], "answer": ["second"], "tags": ["序数词"]},
        {"stem": "I go to bed ______ nine o'clock.", "bank": ["at", "on", "in"], "answer": ["at"], "tags": ["时间表达"]},
    ],
    5: [
        {"stem": "My sister ______ reading story books.", "bank": ["likes", "like", "liking"], "answer": ["likes"], "tags": ["第三人称单数"]},
        {"stem": "There ______ some milk in the glass.", "bank": ["is", "are", "be"], "answer": ["is"], "tags": ["不可数名词"]},
    ],
    6: [
        {"stem": "I ______ a film with my friends last night.", "bank": ["saw", "seen", "see"], "answer": ["saw"], "tags": ["一般过去时"]},
        {"stem": "We are going to ______ a picnic tomorrow.", "bank": ["have", "had", "has"], "answer": ["have"], "tags": ["一般将来时"]},
    ],
}

# ============================================================ 适当形式填空

WORD_FORM_FILL = {
    3: [
        {"stem": "He ______ (be) my brother.", "answer": ["is"], "tags": ["be 动词"]},
        {"stem": "I ______ (have) a small nose.", "answer": ["have"], "tags": []},
    ],
    4: [
        {"stem": "She ______ (like) English very much.", "answer": ["likes"], "tags": ["第三人称单数"]},
        {"stem": "There are two ______ (box) on the desk.", "answer": ["boxes"], "tags": ["名词单复数"]},
    ],
    5: [
        {"stem": "My mother often ______ (go) shopping on Sundays.", "answer": ["goes"], "tags": ["一般现在时"]},
        {"stem": "Look! They ______ (play) football.", "answer": ["are playing"], "tags": ["现在进行时"]},
        {"stem": "This book is ______ (interesting) than that one.", "answer": ["more interesting"], "tags": ["形容词比较级"]},
    ],
    6: [
        {"stem": "We ______ (visit) the museum last week.", "answer": ["visited"], "tags": ["一般过去时"]},
        {"stem": "He ______ (be) going to be a doctor.", "answer": ["is"], "tags": ["一般将来时"]},
        {"stem": "February is the ______ (two) month of the year.", "answer": ["second"], "tags": ["序数词"]},
    ],
}

# ============================================================ 英汉互译

TRANSLATION = {
    3: [
        {"items": [("touch your nose", ["摸你的鼻子"]), ("close your eyes", ["闭上你的眼睛"])], "direction": "e2c", "tags": ["身体部位"]},
        {"items": [("早上好", ["Good morning"])], "direction": "c2e", "tags": []},
    ],
    4: [
        {"items": [("在桌子上", ["on the desk"]), ("在床下面", ["under the bed"])], "direction": "c2e", "tags": ["方位介词"]},
        {"items": [("How much is it?", ["它多少钱？"])], "direction": "e2c", "tags": ["购物消费"]},
    ],
    5: [
        {"items": [("乘公共汽车", ["by bus"]), ("步行回家", ["go home on foot", "walk home"])], "direction": "c2e", "tags": ["交通工具"]},
        {"items": [("take a trip", ["去旅行"])], "direction": "e2c", "tags": []},
    ],
    6: [
        {"items": [("去年夏天", ["last summer"]), ("乘火车回来", ["come back by train", "came back by train"])], "direction": "c2e", "tags": ["一般过去时"]},
        {"items": [("see a doctor", ["看医生"])], "direction": "e2c", "tags": ["看病就医"]},
    ],
}

# ============================================================ 阅读理解（一材多题）

READING_PASSAGES = {
    3: [
        {"title": "阅读短文：My Dog",
         "kind": "reading",
         "body": "I have a dog. Its name is Coco. It is two years old. It is black and white. Coco likes to run and play with a ball. I love my dog very much.",
         "questions": [
            {"stem": "How old is Coco?", "options": ["One.", "Two.", "Three."], "answer": "B", "tags": []},
            {"stem": "What colour is Coco?", "options": ["Black and white.", "Brown.", "Yellow."], "answer": "A", "tags": []},
            {"stem": "What does Coco like to do?", "options": ["Sleep.", "Run and play with a ball.", "Swim."], "answer": "B", "tags": []},
         ]},
    ],
    4: [
        {"title": "阅读短文：Our Classroom",
         "kind": "reading",
         "body": "This is our classroom. It is big and clean. There are forty desks and chairs. There is a blackboard at the front. On the wall there are some pictures. We all like our classroom.",
         "questions": [
            {"stem": "How many desks are there?", "options": ["Thirty.", "Forty.", "Fifty."], "answer": "B", "tags": []},
            {"stem": "What is at the front?", "options": ["A blackboard.", "A computer.", "A map."], "answer": "A", "tags": []},
            {"stem": "What's on the wall?", "options": ["Some pictures.", "Some books.", "Some bags."], "answer": "A", "tags": []},
         ]},
    ],
    5: [
        {"title": "阅读短文：My School Day",
         "kind": "reading",
         "body": "I usually get up at six thirty. I have breakfast at seven. I go to school by bike at seven thirty. School starts at eight. I have four classes in the morning and two in the afternoon. I often play football after school.",
         "questions": [
            {"stem": "How does the writer go to school?", "options": ["By bus.", "By bike.", "On foot."], "answer": "B", "tags": []},
            {"stem": "When does school start?", "options": ["At seven.", "At seven thirty.", "At eight."], "answer": "C", "tags": []},
            {"stem": "What does the writer often do after school?", "options": ["Play football.", "Watch TV.", "Do homework."], "answer": "A", "tags": []},
         ]},
    ],
    6: [
        {"title": "阅读短文：The Dragon Boat Festival",
         "kind": "reading",
         "body": "The Dragon Boat Festival is a Chinese festival. It comes in May or June. People eat zongzi on that day. They also watch dragon boat races. It is a day to remember Qu Yuan, a great poet.",
         "questions": [
            {"stem": "When is the Dragon Boat Festival?", "options": ["In March.", "In May or June.", "In September."], "answer": "B", "tags": []},
            {"stem": "What do people eat?", "options": ["Mooncakes.", "Zongzi.", "Dumplings."], "answer": "B", "tags": []},
            {"stem": "Who was Qu Yuan?", "options": ["A great poet.", "A doctor.", "A teacher."], "answer": "A", "tags": []},
         ]},
    ],
}

# ============================================================ 完形填空

CLOZE_PASSAGES = {
    3: [
        {"title": "完形填空：My Friend",
         "kind": "cloze_text",
         "body": "Hello, I'm Tom. This is my friend, Lily. She [1] eight years old. She has a small cat. [2] cat is white. We often play together.",
         "questions": [
            {"blank_no": 1, "options": ["am", "is", "are"], "answer": "B", "tags": ["be 动词"]},
            {"blank_no": 2, "options": ["His", "Her", "Its"], "answer": "B", "tags": ["物主代词"]},
         ]},
    ],
    4: [
        {"title": "完形填空：My Day",
         "kind": "cloze_text",
         "body": "I get up at six [1] the morning. I go to school [2] bus. My school is not far. I like my school very much.",
         "questions": [
            {"blank_no": 1, "options": ["in", "on", "at"], "answer": "A", "tags": ["时间表达"]},
            {"blank_no": 2, "options": ["by", "on", "in"], "answer": "A", "tags": ["交通工具"]},
         ]},
    ],
    5: [
        {"title": "完形填空：Weekend Plan",
         "kind": "cloze_text",
         "body": "Tomorrow is Saturday. I [1] going to visit my grandparents. I often help them [2] the housework. Then we will cook together.",
         "questions": [
            {"blank_no": 1, "options": ["am", "is", "are"], "answer": "A", "tags": ["一般将来时"]},
            {"blank_no": 2, "options": ["with", "for", "about"], "answer": "A", "tags": []},
         ]},
    ],
    6: [
        {"title": "完形填空：A Busy Weekend",
         "kind": "cloze_text",
         "body": "Last weekend I [1] very busy. On Saturday I visited the science museum. It [2] very interesting. On Sunday I stayed at home and read a book.",
         "questions": [
            {"blank_no": 1, "options": ["am", "was", "were"], "answer": "B", "tags": ["一般过去时"]},
            {"blank_no": 2, "options": ["is", "was", "are"], "answer": "B", "tags": ["一般过去时"]},
         ]},
    ],
}

# ============================================================ 情景对话补全

DIALOGUE = {
    3: [
        {"lines": [{"role": "A", "text": "Hello! I'm Mike. ___", "blank_no": 1}, {"role": "B", "text": "Hi, Mike! My name is Amy."}],
         "pool": [{"key": "A", "text": "What's your name?"}, {"key": "B", "text": "How are you?"}],
         "answers": [["A"]], "mode": "7choose5", "tags": []},
    ],
    4: [
        {"lines": [{"role": "A", "text": "Can I help you?", "blank_no": 0}, {"role": "B", "text": "___", "blank_no": 1}, {"role": "A", "text": "Here you are."}],
         "pool": [{"key": "A", "text": "I want a pen, please."}, {"key": "B", "text": "You're welcome."}],
         "answers": [["A"]], "mode": "7choose5", "tags": ["购物消费"]},
    ],
    5: [
        {"lines": [{"role": "A", "text": "How do you go to school?", "blank_no": 0}, {"role": "B", "text": "___", "blank_no": 1}],
         "pool": [{"key": "A", "text": "I go to school by bike."}, {"key": "B", "text": "It's very far."}],
         "answers": [["A"]], "mode": "7choose5", "tags": ["交通工具"]},
    ],
    6: [
        {"lines": [{"role": "A", "text": "What are you going to do this weekend?", "blank_no": 0}, {"role": "B", "text": "___", "blank_no": 1}],
         "pool": [{"key": "A", "text": "I'm going to visit the museum."}, {"key": "B", "text": "I visited it last year."}],
         "answers": [["A"]], "mode": "7choose5", "tags": ["一般将来时"]},
    ],
}

# ============================================================ 连词成句

UNSCRAMBLE = {
    3: [
        {"words": ["is", "This", "my", "mother", "."], "answer": ["This is my mother."], "tags": ["家庭成员"]},
        {"words": ["have", "I", "a", "pen", "."], "answer": ["I have a pen."], "tags": []},
    ],
    4: [
        {"words": ["is", "the", "cat", "Where", "?"], "answer": ["Where is the cat?"], "tags": ["特殊疑问句"]},
        {"words": ["books", "There", "some", "are", "."], "answer": ["There are some books."], "tags": ["There be 句型"]},
    ],
    5: [
        {"words": ["goes", "school", "She", "to", "bike", "by", "."], "answer": ["She goes to school by bike."], "tags": []},
        {"words": ["than", "is", "Tom", "taller", "Jim", "."], "answer": ["Tom is taller than Jim."], "tags": ["形容词比较级"]},
    ],
    6: [
        {"words": ["went", "I", "zoo", "to", "the", "yesterday", "."], "answer": ["I went to the zoo yesterday."], "tags": ["一般过去时"]},
        {"words": ["going", "are", "We", "have", "to", "picnic", "a", "."], "answer": ["We are going to have a picnic."], "tags": ["一般将来时"]},
    ],
}

# ============================================================ 改写句子

REWRITE = {
    3: [
        {"source": "This is a cat.", "requirement": "改为一般疑问句", "answer": ["Is this a cat?"], "tags": ["一般疑问句"]},
    ],
    4: [
        {"source": "I like apples.", "requirement": "改为一般疑问句", "answer": ["Do you like apples?"], "tags": ["一般疑问句"]},
        {"source": "This is my book.", "requirement": "改为否定句", "answer": ["This isn't my book.", "This is not my book."], "tags": []},
    ],
    5: [
        {"source": "She goes to school by bus.", "requirement": "改为否定句", "answer": ["She doesn't go to school by bus."], "tags": ["一般现在时"]},
        {"source": "Tom is taller than Jim.", "requirement": "改为同义句", "answer": ["Jim is shorter than Tom."], "tags": ["形容词比较级"]},
    ],
    6: [
        {"source": "I went to the park yesterday.", "requirement": "改为否定句", "answer": ["I didn't go to the park yesterday."], "tags": ["一般过去时"]},
        {"source": "He is reading a book.", "requirement": "用 tomorrow 改写", "answer": ["He is going to read a book tomorrow.", "He will read a book tomorrow."], "tags": ["一般将来时"]},
    ],
}

# ============================================================ 看图写话 / 书面表达

WRITING = {
    3: [
        {"t": "picture_writing", "topic": "Look and write", "prompts": ["What can you see?", "How many?", "What colour is it?"],
         "min_sentences": 3, "rubric": [{"point": "用到 3 个以上句子", "score": 3}, {"point": "单词拼写正确", "score": 2}],
         "sample": "I can see three cats. They are black and white. They are very lovely.", "tags": ["动物朋友"]},
    ],
    4: [
        {"t": "picture_writing", "topic": "My Room", "prompts": ["What is in your room?", "Where is it?", "Do you like it?"],
         "min_sentences": 4, "rubric": [{"point": "内容完整", "score": 3}, {"point": "句型正确", "score": 2}],
         "sample": "This is my room. There is a bed and a desk in it. The books are on the desk. I like my room very much.", "tags": ["房间家居"]},
    ],
    5: [
        {"t": "writing", "topic": "My Weekend", "prompts": ["1. Where did you go?", "2. What did you do?", "3. How did you feel?"],
         "min_words": 50,
         "rubric": [{"point": "覆盖三个要点", "score": 6}, {"point": "时态正确", "score": 3}, {"point": "书写与连贯", "score": 1}],
         "sample": "I had a busy weekend. On Saturday I went to the park with my parents. We flew a kite and took many photos. On Sunday I did my homework and read a story book. I felt very happy.",
         "tags": ["一般过去时"]},
    ],
    6: [
        {"t": "writing", "topic": "My Dream Job", "prompts": ["1. What do you want to be?", "2. Why?", "3. What will you do for it?"],
         "min_words": 60,
         "rubric": [{"point": "覆盖三个要点", "score": 6}, {"point": "句式多样且语法正确", "score": 3}, {"point": "书写与连贯", "score": 1}],
         "sample": "I want to be a scientist when I grow up. I think science is interesting and useful. I will study hard and read more books about science. I hope my dream can come true one day.",
         "tags": ["职业理想"]},
    ],
}


class Command(BaseCommand):
    help = "加载三~六年级各题型的内置样例题库"

    def add_arguments(self, parser):
        parser.add_argument("--grade", type=int, help="只加载指定年级（3~6）")
        parser.add_argument("--clear", action="store_true", help="先删除已有的样例题再加载")

    def handle(self, *args, **options):
        grades = [options["grade"]] if options.get("grade") else GRADES
        type_map = {qt.code: qt for qt in QuestionType.objects.all()}

        missing = [c for c in self._required_codes() if c not in type_map]
        if missing:
            self.stderr.write(self.style.ERROR(
                f"缺少题型字典：{missing}。请先执行：python manage.py loaddata fixtures/question_types.json"
            ))
            return

        if options.get("clear"):
            deleted, _ = Question.objects.filter(source_type="sample").hard_delete() \
                if False else (0, 0)
            count = Question.objects.filter(source_type="sample").count()
            Question.objects.filter(source_type="sample").update(is_deleted=True)
            self.stdout.write(f"已标记 {count} 道旧样例题为删除状态")

        created = 0
        with transaction.atomic():
            for grade in grades:
                created += self._load_single_choice(grade, type_map)
                created += self._load_listening_choice(grade, type_map)
                created += self._load_listening_order(grade, type_map)
                created += self._load_judge_passages(grade, type_map)
                created += self._load_banked_fill(grade, type_map)
                created += self._load_word_form_fill(grade, type_map)
                created += self._load_translation(grade, type_map)
                created += self._load_reading(grade, type_map)
                created += self._load_cloze(grade, type_map)
                created += self._load_dialogue(grade, type_map)
                created += self._load_unscramble(grade, type_map)
                created += self._load_rewrite(grade, type_map)
                created += self._load_writing(grade, type_map)

        self.stdout.write(self.style.SUCCESS(f"完成：新增 {created} 道样例题（年级 {grades}）"))

    # ------------------------------------------------------------ 内部工具

    def _required_codes(self):
        return [
            "listening_choice", "listening_order", "listening_judge", "single_choice",
            "banked_fill", "word_form_fill", "translation", "reading_choice",
            "reading_judge", "cloze", "dialogue_completion", "sentence_unscramble",
            "sentence_rewrite", "picture_writing", "writing",
        ]

    def _tags(self, tag_names):
        tags = []
        for name in tag_names or []:
            if not name:
                continue
            if ":" in name:
                category, real_name = name.split(":", 1)
            else:
                category, real_name = "grammar_point", name
            tag, _ = Tag.objects.get_or_create(
                name=real_name.strip(), category=category.strip(),
                defaults={"is_system": True},
            )
            tags.append(tag)
        return tags

    def _create(self, question_type, *, grade, stem="", content=None, answer=None,
                explanation="", tags=None, passage=None, sequence=0, score=None):
        """统一的建题入口，自动跳过重复。"""
        question = Question(
            question_type=question_type,
            grade=grade,
            term="全",
            difficulty=3,
            stem=stem,
            content=content or {"v": 1},
            answer=answer or {"v": 1},
            explanation=explanation,
            suggested_score=score if score is not None else question_type.default_score,
            review_status="approved",
            source_type="sample",
            passage=passage,
            sequence=sequence,
        )
        if question.find_duplicate() is not None:
            return 0
        question.save()
        for tag in self._tags(tags):
            question.tags.add(tag)
        return 1

    # ------------------------------------------------------------ 各题型

    def _load_single_choice(self, grade, type_map):
        count = 0
        for item in SINGLE_CHOICE.get(grade, []):
            content = {
                "v": 1,
                "options": [{"key": chr(65 + i), "text": t, "image_id": None}
                            for i, t in enumerate(item["options"])],
                "layout": {"options": "vertical"},
            }
            count += self._create(
                type_map["single_choice"], grade=grade, stem=item["stem"],
                content=content, answer={"v": 1, "type": "single_choice", "value": [item["answer"]]},
                explanation=item.get("explanation", ""), tags=item.get("tags"),
            )
        return count

    def _load_listening_choice(self, grade, type_map):
        count = 0
        for stem, options, answer, tags in LISTENING_CHOICE.get(grade, []):
            content = {
                "v": 1,
                "mode": "word",
                "options": [{"key": chr(65 + i), "text": t, "image_id": None}
                            for i, t in enumerate(options)],
                "layout": {"options": "grid4"},
            }
            count += self._create(
                type_map["listening_choice"], grade=grade, stem=stem,
                content=content, answer={"v": 1, "type": "single_choice", "value": [answer]},
                tags=tags,
            )
        return count

    def _load_listening_order(self, grade, type_map):
        count = 0
        for items, answer, tags in LISTENING_ORDER.get(grade, []):
            content = {
                "v": 1,
                "items": [{"i": i + 1, "text": t} for i, t in enumerate(items)],
                "shuffle": True,
            }
            count += self._create(
                type_map["listening_order"], grade=grade, stem="听录音，给下列句子排序。",
                content=content, answer={"v": 1, "type": "order", "value": answer},
                tags=tags,
            )
        return count

    def _load_judge_passages(self, grade, type_map):
        count = 0
        for spec in PASSAGE_JUDGE.get(grade, []):
            passage = Passage.objects.filter(title=spec["title"], kind=spec["kind"]).first()
            if passage is None:
                passage = Passage.objects.create(
                    title=spec["title"], kind=spec["kind"], grade=grade, body=spec["body"]
                )
            question_type = type_map[spec["type"]]
            content = {
                "v": 1,
                "statements": [{"no": i + 1, "text": t} for i, (t, _) in enumerate(spec["statements"])],
            }
            answer = {"v": 1, "type": "tf", "value": [bool(a) for _, a in spec["statements"]]}
            count += self._create(
                question_type, grade=grade, stem="听录音 / 阅读短文，判断下列句子的正（T）误（F）。",
                content=content, answer=answer, passage=passage,
            )
        return count

    def _load_banked_fill(self, grade, type_map):
        count = 0
        for item in BANKED_FILL.get(grade, []):
            content = {
                "v": 1,
                "word_bank": item["bank"],
                "blanks": [{"no": 1}],
                "bank_extra": max(len(item["bank"]) - 1, 0),
            }
            answer = {"v": 1, "type": "blanks", "value": [{"no": 1, "value": item["answer"]}]}
            count += self._create(
                type_map["banked_fill"], grade=grade, stem=item["stem"].replace("______", "___"),
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_word_form_fill(self, grade, type_map):
        count = 0
        for item in WORD_FORM_FILL.get(grade, []):
            given = ""
            import re as _re
            match = _re.search(r"\((\w+)\)", item["stem"])
            if match:
                given = match.group(1)
            content = {"v": 1, "blanks": [{"no": 1, "given": given}]}
            answer = {"v": 1, "type": "blanks", "value": [{"no": 1, "value": item["answer"]}]}
            count += self._create(
                type_map["word_form_fill"], grade=grade,
                stem=item["stem"].replace("______", "___"),
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_translation(self, grade, type_map):
        count = 0
        for item in TRANSLATION.get(grade, []):
            items = [{"no": i + 1, "src": src} for i, (src, _) in enumerate(item["items"])]
            content = {"v": 1, "direction": item.get("direction", "e2c"), "items": items}
            answer = {
                "v": 1, "type": "blanks",
                "value": [{"no": i + 1, "value": ans} for i, (_, ans) in enumerate(item["items"])],
            }
            label = "英译汉" if content["direction"] == "e2c" else "汉译英"
            count += self._create(
                type_map["translation"], grade=grade, stem=f"翻译下列内容（{label}）。",
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_reading(self, grade, type_map):
        count = 0
        for spec in READING_PASSAGES.get(grade, []):
            passage = Passage.objects.filter(title=spec["title"]).first()
            if passage is None:
                passage = Passage.objects.create(
                    title=spec["title"], kind=spec["kind"], grade=grade, body=spec["body"]
                )
            for index, q in enumerate(spec["questions"], start=1):
                content = {
                    "v": 1,
                    "options": [{"key": chr(65 + i), "text": t, "image_id": None}
                                for i, t in enumerate(q["options"])],
                    "layout": {"options": "vertical"},
                }
                count += self._create(
                    type_map["reading_choice"], grade=grade, stem=q["stem"],
                    content=content,
                    answer={"v": 1, "type": "single_choice", "value": [q["answer"]]},
                    explanation=q.get("explanation", ""), tags=q.get("tags"),
                    passage=passage, sequence=index,
                )
        return count

    def _load_cloze(self, grade, type_map):
        count = 0
        for spec in CLOZE_PASSAGES.get(grade, []):
            passage = Passage.objects.filter(title=spec["title"]).first()
            if passage is None:
                passage = Passage.objects.create(
                    title=spec["title"], kind=spec["kind"], grade=grade, body=spec["body"]
                )
            for q in spec["questions"]:
                content = {
                    "v": 1,
                    "blank_no": q["blank_no"],
                    "options": [{"key": chr(65 + i), "text": t, "image_id": None}
                                for i, t in enumerate(q["options"])],
                    "layout": {"options": "vertical"},
                }
                count += self._create(
                    type_map["cloze"], grade=grade, stem=f"第 {q['blank_no']} 空",
                    content=content,
                    answer={"v": 1, "type": "single_choice", "value": [q["answer"]]},
                    tags=q.get("tags"), passage=passage, sequence=q["blank_no"],
                )
        return count

    def _load_dialogue(self, grade, type_map):
        count = 0
        for item in DIALOGUE.get(grade, []):
            content = {
                "v": 1,
                "mode": item.get("mode", "open"),
                "roles": ["A", "B"],
                "lines": item["lines"],
                "pool": item.get("pool", []),
            }
            answer = {
                "v": 1, "type": "blanks",
                "value": [{"no": i + 1, "value": v} for i, v in enumerate(item["answers"])],
            }
            count += self._create(
                type_map["dialogue_completion"], grade=grade,
                stem="根据对话内容，从方框中选择合适的句子补全对话。",
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_unscramble(self, grade, type_map):
        count = 0
        for item in UNSCRAMBLE.get(grade, []):
            content = {
                "v": 1,
                "words": item["words"],
                "distractors": item.get("distractors", []),
                "punct_included": True,
            }
            answer = {"v": 1, "type": "blanks", "value": [{"no": 1, "value": item["answer"]}]}
            count += self._create(
                type_map["sentence_unscramble"], grade=grade, stem="连词成句。",
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_rewrite(self, grade, type_map):
        count = 0
        for item in REWRITE.get(grade, []):
            content = {
                "v": 1,
                "source": item["source"],
                "requirement": item["requirement"],
                "keep_marker": True,
            }
            answer = {"v": 1, "type": "blanks", "value": [{"no": 1, "value": item["answer"]}]}
            count += self._create(
                type_map["sentence_rewrite"], grade=grade, stem="按要求改写句子。",
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count

    def _load_writing(self, grade, type_map):
        count = 0
        for item in WRITING.get(grade, []):
            code = item["t"]
            content = {"v": 1, "topic": item["topic"], "prompts": item["prompts"]}
            if item.get("min_words"):
                content["min_words"] = item["min_words"]
            if item.get("min_sentences"):
                content["min_sentences"] = item["min_sentences"]
            answer = {
                "v": 1, "type": "rubric",
                "rubric": item["rubric"],
                "sample": [item["sample"]],
            }
            count += self._create(
                type_map[code], grade=grade, stem="书面表达。",
                content=content, answer=answer, tags=item.get("tags"),
            )
        return count
