# accounts/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()

@receiver(pre_save, sender=User)
def clear_flag_on_password_change(sender, instance, **kwargs):
    """
    Si el hash de la contraseña cambió, apaga Profile.must_change_password.
    """
    if not instance.pk:
        return  # usuario nuevo; no hay estado previo para comparar

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # ¿La contraseña cambió?
    if old.password != instance.password:
        try:
            prof = instance.profile  # acceso reverso OneToOne
        except ObjectDoesNotExist:
            return
        if getattr(prof, "must_change_password", False):
            prof.must_change_password = False
            prof.save(update_fields=["must_change_password"])

