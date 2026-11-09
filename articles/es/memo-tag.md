---
title: "Memo, etiqueta y destino del pago al intercambiar: dónde ingresarlo y qué ocurre al cometer un error"
description: "Cómo rellenar correctamente el campo memo/etiqueta en el proceso de intercambio de criptomonedas, dónde se encuentra y qué consecuencias pueden surgir por un ingreso incorrecto."
date: 2026-11-09
slug: memo-tag
---

# Memo, etiqueta y destino del pago al intercambiar: dónde ingresarlo y qué ocurre al cometer un error

## ## ¿Dónde se encuentra el campo memo/etiqueta en la interfaz del intercambiador

Al realizar un intercambio de criptomonedas a través de un portal web o una aplicación móvil, normalmente existe una línea separada para ingresar un identificador adicional. Este campo puede estar justo debajo del campo de la dirección del destinatario, en la sección «Parámetros adicionales», o en un paso aparte de «Confirmación» antes de enviar la transacción. En algunas carteras (por ejemplo, Exodus, Trust Wallet) el mismo campo aparece en la pantalla «Enviar», donde después de ingresar la dirección se muestra la etiqueta «Memo / Tag (si se requiere)». En plataformas P2P a menudo se requiere indicarlo en la descripción del pedido o en el comentario del pago. La posición del campo puede variar según el intercambio específico, pero su presencia siempre se confirma en las instrucciones del intercambiador.

## ## Cómo rellenar correctamente memo/etiqueta

El campo memo/etiqueta se utiliza solo donde la blockchain requiere un parámetro adicional para identificar de forma única al destinatario. Por ejemplo, en la red Ripple (XRP) y Stellar (XLM) el valor tag es obligatorio, y su ausencia provoca la rejección de la transacción. En la red TRON (TRX) y algunos tokens ERC‑20 (por ejemplo, USDT) el campo es opcional, pero si el intercambiador lo solicita debe ingresarse exactamente como indica su soporte. Para evitar errores, se recomienda:

- verificar si ese parámetro es requerido para la red seleccionada (a veces se indica en la sección «Requisitos de pago»);
- copiar el valor desde el recibo del destinatario, el mensaje de confirmación o los detalles de la transacción que planeas enviar;
- ingresar los caracteres sin espacios ni signos innecesarios, ya que incluso un pequeño error puede hacer que el pago sea no rastreable.

## ## Consecuencias de un error en el campo memo/etiqueta

Si el memo/etiqueta está incorrecto o se omite por completo cuando es obligatorio, la transacción puede ser rechazada durante la verificación y no se enviará, lo que generalmente se refleja en un mensaje «Invalid tag» o «Missing memo». En casos en los que el campo es opcional, pero se ingresa un valor erróneo, la blockchain normalmente acepta la transacción, aunque los fondos pueden terminar en otro usuario si la dirección del destinatario coincide con quien usa ese tag. En la mayoría de las blockchains no es posible rastrear por un tag incorrecto, por lo que recuperar los fondos sin ayuda técnica será muy difícil. Algunos intercambiadores cancelan automáticamente estas operaciones y devuelven los fondos al saldo, pero solo ocurre cuando hay un error evidente en la dirección, no solo en el tag. Por eso es importante verificar tanto la dirección como el identificador adicional.

## ## Cómo minimizar el riesgo al trabajar con memo/etiqueta

- siempre verifica el formato requerido (número, cadena, combinación) en la documentación de referencia del intercambiador;
- al trabajar en intercambios P2P, copia el tag del mensaje del comprador o del vendedor;
- después de completar el formulario usa el botón «Vista previa» (si está disponible) y verifica que el campo se muestre correctamente;
- en caso de duda, contacta al servicio de soporte proporcionando el hash de la transacción y el tag indicado.

**Tabla: Dónde se ingresa memo/etiqueta y consecuencias típicas del error**

| Dónde se ingresa | Consecuencias típicas del error |
|------------------|--------------------------------|
| En la etapa de ingreso de la dirección en la interfaz web del intercambiador | La transacción puede ser rechazada si el tag es obligatorio; de lo contrario, los fondos pueden enviarse sin indicar al destinatario y perderse |
| En la aplicación móvil «Enviar» de la billetera | Si falta el tag obligatorio, se cancela; si el valor es incorrecto, puede haber pérdida de fondos y se necesita soporte técnico |
| En un pedido P2P (descripción del pago) | Un tag erróneo puede impedir que el dinero se acredite a la cuenta del vendedor y requiera abrir una disputa |
