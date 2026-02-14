"""
페이지 라우터 - Jinja2 템플릿 페이지 라우트를 동적으로 등록
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

# 정적 페이지 라우트: (path, template_file)
_PAGE_ROUTES = [
    ("/", "index.html"),
    ("/networks", "networks.html"),
    ("/images", "images.html"),
    ("/volumes", "volumes.html"),
    ("/logs", "logs.html"),
    ("/compose", "compose.html"),
    ("/system", "system.html"),
]


def _make_page_handler(template_name: str):
    """템플릿 이름으로 페이지 핸들러를 생성하는 팩토리"""
    async def handler(request: Request):
        return templates.TemplateResponse(template_name, {"request": request})
    handler.__name__ = f"page_{template_name.replace('.html', '')}"
    return handler


# 정적 페이지 라우트 등록
for path, template in _PAGE_ROUTES:
    router.add_api_route(path, _make_page_handler(template), methods=["GET"], response_class=HTMLResponse)


# Inspect 페이지는 path parameter가 있어 별도 등록
@router.get("/inspect/{container_id}", response_class=HTMLResponse)
async def get_inspect_page(request: Request, container_id: str):
    """컨테이너 상세 Inspect 페이지"""
    return templates.TemplateResponse("inspect.html", {"request": request, "container_id": container_id})
