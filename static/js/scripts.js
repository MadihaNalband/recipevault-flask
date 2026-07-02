document.addEventListener("DOMContentLoaded", () => {
    const recipeForm = document.getElementById("recipe-form");
    const recipeList = document.getElementById("recipe-list");

    //Fetch user-specific recipes
    const fetchRecipes = async () => {
        const response = await fetch("/get_recipes");
        const recipes = await response.json();
        renderRecipes(recipes);
    };

    //Render recipes
    const renderRecipes = (recipes) => {
        recipeList.innerHTML = "";
        recipes.forEach(recipe => {
            const li = document.createElement("li");
            li.innerHTML = `
                <h3>${recipe.name}</h3>
                <p><strong>Ingredients:</strong> ${recipe.ingredients}</p>
                <p><strong>Steps:</strong> ${recipe.steps}</p>
            `;
            recipeList.appendChild(li);
        });
    };

    //Add new recipe
    recipeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = document.getElementById("recipe-name").value;
        const ingredients = document.getElementById("recipe-ingredients").value;
        const steps = document.getElementById("recipe-steps").value;

        const response = await fetch("/add_recipe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, ingredients, steps })
        });
        const result = await response.json();
        renderRecipes(result.recipes);

        recipeForm.reset();
    });

    fetchRecipes();
});
