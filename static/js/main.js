let cart = JSON.parse(
    localStorage.getItem("sportshop_cart")
) || [];


// ==========================================
// ADD TO CART
// ==========================================

function addToCart(id, name, price) {
    const existingProduct = cart.find(
        product => product.id === id
    );

    if (existingProduct) {
        existingProduct.quantity += 1;
    } else {
        cart.push({
            id: id,
            name: name,
            price: price,
            quantity: 1
        });
    }

    localStorage.setItem(
        "sportshop_cart",
        JSON.stringify(cart)
    );

    window.location.href = "/cart";
}

// ==========================================
// LOAD CART PAGE
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const cartItems =
            document.getElementById("cartItems");

        if (!cartItems) {
            return;
        }


        displayCart();

    }
);


// ==========================================
// DISPLAY CART
// ==========================================

function displayCart() {

    const cartItems =
        document.getElementById("cartItems");

    const totalItems =
        document.getElementById("totalItems");

    const totalAmount =
        document.getElementById("totalAmount");


    if (!cartItems) {
        return;
    }


    if (cart.length === 0) {

        cartItems.innerHTML = `

            <div class="empty-cart">

                <h2>
                    Your cart is empty 🛒
                </h2>

                <p>
                    Add some sports products to your cart.
                </p>

                <a href="/products"
                   class="btn">

                    Continue Shopping

                </a>

            </div>

        `;

        totalItems.textContent = "0";

        totalAmount.textContent = "₹0.00";

        return;
    }


    cartItems.innerHTML = "";

    let items = 0;

    let total = 0;


    cart.forEach(
        function (product, index) {

            const itemTotal =
                product.price *
                product.quantity;


            items += product.quantity;

            total += itemTotal;


            cartItems.innerHTML += `

                <div class="cart-item">

                    <div class="cart-product-info">

                        <h3>
                            ${product.name}
                        </h3>

                        <p>
                            ₹${product.price.toFixed(2)}
                        </p>

                    </div>


                    <div class="quantity-control">

                        <button
                            onclick="decreaseQuantity(${index})">

                            −

                        </button>

                        <span>
                            ${product.quantity}
                        </span>

                        <button
                            onclick="increaseQuantity(${index})">

                            +

                        </button>

                    </div>


                    <div class="cart-item-total">

                        ₹${itemTotal.toFixed(2)}

                    </div>


                    <button
                        class="remove-btn"
                        onclick="removeFromCart(${index})">

                        Remove

                    </button>

                </div>

            `;

        }
    );


    totalItems.textContent =
        items;


    totalAmount.textContent =
        "₹" + total.toFixed(2);

}


// ==========================================
// INCREASE QUANTITY
// ==========================================

function increaseQuantity(index) {

    cart[index].quantity += 1;

    saveCart();

    displayCart();

}


// ==========================================
// DECREASE QUANTITY
// ==========================================

function decreaseQuantity(index) {

    if (
        cart[index].quantity > 1
    ) {

        cart[index].quantity -= 1;

    } else {

        cart.splice(index, 1);

    }


    saveCart();

    displayCart();

}


// ==========================================
// REMOVE PRODUCT
// ==========================================

function removeFromCart(index) {

    cart.splice(index, 1);

    saveCart();

    displayCart();

}


// ==========================================
// SAVE CART
// ==========================================

function saveCart() {

    localStorage.setItem(
        "sportshop_cart",
        JSON.stringify(cart)
    );

}


// ==========================================
// CHECKOUT
// ==========================================

function goToCheckout() {

    if (cart.length === 0) {

        alert(
            "Your cart is empty!"
        );

        return;
    }


    window.location.href =
        "/checkout";

}

