import re
from typing import Dict, Any, Optional


def parse_boss_subject(subject: str) -> Dict[str, Any]:
    """
    解析BOSS直聘邮件主题，提取候选人信息

    格式示例:
    - 任承智 | 27年应届生，应聘 暖通工程师 | 南通10-15K【BOSS直聘】
    - 张三 | 5年经验，应聘 Java开发工程师 | 北京20-30K【BOSS直聘】
    - 李四 | 应聘 产品经理 | 上海15-25K【BOSS直聘】

    Returns:
        {
            "candidate_name": "任承智",
            "experience": "27年应届生",
            "job_title": "暖通工程师",
            "location": "南通",
            "salary": "10-15K",
            "source": "BOSS直聘"
        }
    """
    result = {
        "candidate_name": None,
        "experience": None,
        "job_title": None,
        "location": None,
        "salary": None,
        "source": "BOSS直聘"
    }

    if not subject:
        return result

    # 移除末尾的【BOSS直聘】标记
    clean_subject = re.sub(r'【BOSS直聘】$', '', subject).strip()

    # 尝试匹配: 名字 | 经验，应聘 岗位 | 地点薪资
    # 模式1: 名字 | 经验，应聘 岗位 | 地点薪资
    pattern1 = r'^(.*?)\s*\|\s*(.*?)\s*应聘\s+(.*?)\s*\|\s*(.*?)(\d+[\d\-Kk]+)[\s\/]*(.*?)\s*$'
    match1 = re.search(pattern1, clean_subject)

    if match1:
        result["candidate_name"] = match1.group(1).strip()
        result["experience"] = match1.group(2).strip().rstrip('，').rstrip(',')
        result["job_title"] = match1.group(3).strip()
        result["location"] = match1.group(4).strip()
        result["salary"] = match1.group(5).strip().upper()
        return result

    # 模式2: 名字 | 应聘 岗位 | 地点薪资 (无经验)
    pattern2 = r'^(.*?)\s*\|\s*应聘\s+(.*?)\s*\|\s*(.*?)(\d+[\d\-Kk]+)[\s\/]*(.*?)\s*$'
    match2 = re.search(pattern2, clean_subject)

    if match2:
        result["candidate_name"] = match2.group(1).strip()
        result["job_title"] = match2.group(2).strip()
        result["location"] = match2.group(3).strip()
        result["salary"] = match2.group(4).strip().upper()
        return result

    # 模式3: 简单尝试用 | 分割
    parts = [p.strip() for p in clean_subject.split('|')]
    if len(parts) >= 3:
        result["candidate_name"] = parts[0]
        # 中间部分尝试提取"应聘"后面的岗位
        middle = parts[1]
        if '应聘' in middle:
            job_match = re.search(r'应聘\s+(.+)', middle)
            if job_match:
                result["job_title"] = job_match.group(1).strip()
            # 经验是"应聘"前面的部分
            exp_part = middle.split('应聘')[0].strip().rstrip('，').rstrip(',')
            if exp_part:
                result["experience"] = exp_part
        else:
            result["job_title"] = middle

        # 最后部分尝试提取地点和薪资
        last = parts[2]
        salary_match = re.search(r'(\d+[\d\-Kk]+)', last)
        if salary_match:
            result["salary"] = salary_match.group(1).upper()
            # 薪资前面的可能是地点
            loc_part = last[:salary_match.start()].strip()
            if loc_part:
                result["location"] = loc_part
        else:
            result["location"] = last

        return result

    # 兜底：如果只有一个 |，尝试提取
    if len(parts) == 2:
        result["candidate_name"] = parts[0]
        result["job_title"] = parts[1]
        return result

    return result


def parse_boss_email_body(html_body: str) -> Dict[str, Any]:
    """
    从BOSS直聘邮件HTML正文中提取更多信息

    Returns:
        {
            "candidate_phone": "138****1234",
            "candidate_email": "xxx@qq.com",
            "education": "本科",
            "school": "某某大学",
            "work_years": "3年"
        }
    """
    result = {
        "candidate_phone": None,
        "candidate_email": None,
        "education": None,
        "school": None,
        "work_years": None
    }

    if not html_body:
        return result

    # 尝试从HTML中提取手机号
    phone_pattern = r'(1[3-9]\d{9}|1[3-9]\d\*{4}\d{4})'
    phone_match = re.search(phone_pattern, html_body)
    if phone_match:
        result["candidate_phone"] = phone_match.group(1)

    # 尝试提取邮箱
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    email_match = re.search(email_pattern, html_body)
    if email_match:
        email = email_match.group(0)
        # 排除BOSS直聘官方邮箱
        if 'bosszhipin.com' not in email and 'service' not in email:
            result["candidate_email"] = email

    # 尝试提取学历
    edu_keywords = ['博士', '硕士', '本科', '大专', '中专', '高中']
    for edu in edu_keywords:
        if edu in html_body:
            result["education"] = edu
            break

    # 尝试提取工作年限
    years_pattern = r'(\d+)\s*年(?:经验|工作|以上)?'
    years_match = re.search(years_pattern, html_body)
    if years_match:
        result["work_years"] = years_match.group(1) + "年"

    return result


def get_resume_source(sender_email: str) -> str:
    """根据发件人邮箱判断简历来源"""
    source_map = {
        'bosszhipin.com': 'BOSS直聘',
        'zhaopin.com': '智联招聘',
        '51job.com': '前程无忧',
        'liepin.com': '猎聘',
        'lagou.com': '拉勾',
        'linkedin.com': 'LinkedIn',
        'mail.tm': '邮件投递',
        'wshu.net': '邮件投递'
    }

    sender_lower = sender_email.lower()
    for domain, source in source_map.items():
        if domain in sender_lower:
            return source

    return '邮件投递'


def extract_contact_from_pdf_filename(filename: str) -> Optional[str]:
    """
    从PDF文件名中提取候选人姓名
    BOSS直聘文件名通常包含候选人信息
    """
    if not filename:
        return None

    # 移除时间前缀和cv_前缀
    clean = re.sub(r'^\d{8}_\d{6}_cv_', '', filename)
    clean = re.sub(r'\.pdf$', '', clean, flags=re.IGNORECASE)

    # 尝试提取中文姓名（通常是连续的中文汉字，2-4个字）
    chinese_name_pattern = r'[一-龥]{2,4}'
    names = re.findall(chinese_name_pattern, clean)
    if names:
        # 返回第一个可能是姓名的（排除常见的职位、地点关键词）
        exclude_words = ['工程师', '经理', '主管', '专员', '总监', '助理', '顾问',
                        '北京', '上海', '广州', '深圳', '杭州', '成都', '武汉',
                        '南京', '苏州', '南通', '以内', '以上', '经验']
        for name in names:
            if name not in exclude_words and len(name) >= 2:
                return name

    return None
