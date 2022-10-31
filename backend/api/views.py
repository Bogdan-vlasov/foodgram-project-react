from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from api.filters import AuthorAndTagFilter, IngredientSearchFilter
from api.models import (Cart, Favorite, Ingredient, IngredientAmount, Recipe,
                        Tag)
from api.pagination import LimitPageNumberPagination
from api.permissions import IsAdminOrReadOnly, AuthorOrReadOnly
from api.serializers import (CropRecipeSerializer, IngredientSerializer,
                             RecipeSerializer, TagSerializer)


class TagsViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAdminOrReadOnly,)
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientsViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAdminOrReadOnly,)
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (IngredientSearchFilter,)
    search_fields = ('^name',)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    pagination_class = LimitPageNumberPagination
    filter_class = AuthorAndTagFilter
    permission_classes = [AuthorOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self.add_obj(Favorite, request.user, pk)
        elif request.method == 'DELETE':
            return self.delete_obj(Favorite, request.user, pk)
        return None

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.add_obj(Cart, request.user, pk)
        elif request.method == 'DELETE':
            return self.delete_obj(Cart, request.user, pk)
        return Response({
            'errors': 'Неверный метод'
        }, status=status.HTTP_400_BAD_REQUEST)

    def add_obj(self, model, user, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response({
                'errors': 'Рецепт уже добавлен в список'
            }, status=status.HTTP_400_BAD_REQUEST)
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = CropRecipeSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_obj(self, model, user, pk):
        obj = model.objects.filter(user=user, recipe__id=pk)
        if obj.exists():
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({
            'errors': 'Рецепт уже удален'
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        download_dict = {}
        ingredients = IngredientAmount.objects.filter(
            recipe__cart__user=request.user).values_list(
                'ingredient__name',
                'ingredient__measurement_unit',
                ).annotate(total_amount=Sum('amount'))
        for name, (amount, units) in ingredients:
            name = ingredients['ingredient__name']
            units = ingredients['ingredient__measurement_unit']
            amount = ingredients['total_amount']
            if name in download_dict:
                new_amount = download_dict[name][0] + amount
                download_dict[name] = (new_amount, units)
            else:
                download_dict[name] = (amount, units)
        response = HttpResponse(content_type='.txt')
        response.write('\n'.join(f'{name} - {amount} {units}'
                       for name, (amount, units) in download_dict.items()))
        return response

