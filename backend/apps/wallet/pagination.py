"""Envelope-style pagination for wallet history.

Response shape::

    {
      "success": true,
      "message": "OK",
      "data": [...items...],
      "pagination": {"page": 1, "page_size": 20, "count": 123, "pages": 7}
    }
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class EnvelopePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                'success': True,
                'message': 'OK',
                'data': data,
                'pagination': {
                    'page': self.page.number,
                    'page_size': self.get_page_size(self.request),
                    'count': self.page.paginator.count,
                    'pages': self.page.paginator.num_pages,
                },
            }
        )
