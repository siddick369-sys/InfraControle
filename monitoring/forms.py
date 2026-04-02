from django import forms
from .models import *


class EquipementReseauForm(forms.ModelForm):
    # On définit les styles communs pour éviter la répétition
    common_attrs = {'class': 'form-control tech-input'}

    mot_de_passe_ssh = forms.CharField(
        widget=forms.PasswordInput(attrs={**common_attrs, 'placeholder': '••••••••'}),
        label="Clé d'accès (Password)",
        required=False,
        help_text="Laissez vide pour conserver le mot de passe actuel lors d'une modification ou si SSH n'est pas utilisé."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si on modifie (instance.pk existe), le mot de passe n'est plus obligatoire
        if self.instance and self.instance.pk:
            self.fields['mot_de_passe_ssh'].required = False

    class Meta:
        model = EquipementReseau
        common_attrs = {'class': 'form-control tech-input'}
        fields = [
            'nom', 'type_equipement', 'adresse_ip', 
            'port_ssh', 'utilisateur_ssh', 'mot_de_passe_ssh', 
            'localisation', 'description', 'actif'
        ]
        
        widgets = {
            'nom': forms.TextInput(attrs={**common_attrs, 'placeholder': "Ex: SW-CORE-01"}),
            'type_equipement': forms.Select(attrs={'class': 'form-select tech-input'}),
            'adresse_ip': forms.TextInput(attrs={**common_attrs, 'placeholder': "192.168.x.x"}),
            'port_ssh': forms.NumberInput(attrs={**common_attrs, 'placeholder': "22"}),
            'utilisateur_ssh': forms.TextInput(attrs={**common_attrs, 'placeholder': "admin"}),
            'localisation': forms.TextInput(attrs={**common_attrs, 'placeholder': "Rack A2"}),
            'description': forms.Textarea(attrs={**common_attrs, 'rows': 3, 'placeholder': "Détails techniques..."}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input tech-switch'}),
        }

    def save(self, commit=True):
        equipement = super().save(commit=False)
        new_pass = self.cleaned_data.get('mot_de_passe_ssh')
        if new_pass:
            equipement.set_mot_de_passe_ssh(new_pass)
        
        if commit:
            equipement.save()
        return equipement
    
    
class ChangePlanifieForm(forms.ModelForm):
    class Meta:
        model = ChangePlanifie
        fields = [
            "equipement",
            "frequence",
            "date_execution",
            "actif",
        ]
        widgets = {
            "date_execution": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            )
        }
        
        
# monitoring/forms.py

from django import forms
from monitoring.models import CommandeAutomatique, ChangePlanifie

class CommandeAutomatiqueForm(forms.ModelForm):
    class Meta:
        model = CommandeAutomatique
        fields = [
            "nom",
            "description",
            "contenu",
            "applicable_pour",
            "confirmation_requise",
            "critique",
        ]
        widgets = {
            "contenu": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "ex:\nsudo systemctl restart ssh\nsudo reboot"
                }
            ),
            "description": forms.Textarea(attrs={"rows": 3}),
            "applicable_pour": forms.CheckboxSelectMultiple(),
        }
        
# monitoring/forms.py

class ValidationChangeForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[
            ("valide", "✅ Valider"),
            ("rejete", "❌ Rejeter"),
        ],
        widget=forms.RadioSelect
    )
    commentaire = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )

import re

class PlanificationDirecteForm(forms.ModelForm):
    commande_texte = forms.CharField(
        label="Commande à exécuter",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "ex: systemctl restart nginx, df -h"}),
        help_text="Les commandes destructrices seront bloquées (rm, reboot, etc.)"
    )

    class Meta:
        model = ChangePlanifie
        fields = [
            "commande_texte",
            "frequence",
            "date_execution",
        ]
        widgets = {
            "date_execution": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "frequence": forms.Select(attrs={"class": "form-select"})
        }

    def clean_commande_texte(self):
        cmd = self.cleaned_data.get('commande_texte', '')
        
        mots_interdits = [
            r'\brm\b', r'\breboot\b', r'\bshutdown\b', r'\bmkfs\b', 
            r'\bhalt\b', r'\bpoweroff\b', r'\binit 0\b', r'\binit 6\b',
            r'\bpasswd\b', r'\bchmod\b', r'\bchown\b', r'\bdd\b', r'\bmv\s+/',
            r'>\s*/(dev|etc|boot|sys|proc|bin|sbin|var|usr|lib)', r'>>\s*/(dev|etc|boot|sys|proc|bin|sbin|var|usr|lib)'
        ]
        
        for motif in mots_interdits:
            if re.search(motif, cmd):
                raise forms.ValidationError(f"Commande interdite. Le motif '{motif}' n'est pas autorisé pour des raisons de sécurité.")
                
        return cmd