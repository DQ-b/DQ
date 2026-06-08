using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class WeaponsBuilder
{
    [MenuItem("LittleSoldier/Setup Weapons")]
    public static void Setup()
    {
        GameObject player = GameObject.Find("Player");
        if (player == null)
        {
            Debug.LogError("Player was not found. Make sure the training scene is already generated.");
            return;
        }

        Camera cameraComponent = player.GetComponentInChildren<Camera>(true);
        if (cameraComponent == null && Camera.main != null)
            cameraComponent = Camera.main;

        if (cameraComponent == null)
        {
            Debug.LogError("Main Camera was not found.");
            return;
        }

        GameObject cameraObject = cameraComponent.gameObject;
        cameraComponent.nearClipPlane = 0.03f;

        GunRaycast oldGun = cameraObject.GetComponent<GunRaycast>();
        if (oldGun != null)
            Object.DestroyImmediate(oldGun);

        AudioSource audioSource = cameraObject.GetComponent<AudioSource>();
        if (audioSource == null)
            audioSource = cameraObject.AddComponent<AudioSource>();
        audioSource.playOnAwake = false;

        WeaponController weaponController = cameraObject.GetComponent<WeaponController>();
        if (weaponController == null)
            weaponController = cameraObject.AddComponent<WeaponController>();

        WeaponView weaponView = cameraObject.GetComponent<WeaponView>();
        if (weaponView == null)
            weaponView = cameraObject.AddComponent<WeaponView>();
        weaponView.BuildDefaultViewModels();

        weaponController.weapons = new Weapon[]
        {
            new Weapon
            {
                name = "\u624b\u67aa",
                damage = 25f,
                fireRate = 3f,
                magazineSize = 12,
                reserveAmmo = 48,
                reloadTime = 1.1f,
                spread = 0.004f,
                recoil = 1.2f,
                automatic = false,
                range = 100f
            },
            new Weapon
            {
                name = "\u6b65\u67aa",
                damage = 18f,
                fireRate = 8f,
                magazineSize = 30,
                reserveAmmo = 120,
                reloadTime = 1.6f,
                spread = 0.02f,
                recoil = 1.6f,
                automatic = true,
                range = 120f
            },
            new Weapon
            {
                name = "\u52a0\u7279\u6797",
                damage = 10f,
                fireRate = 18f,
                magazineSize = 100,
                reserveAmmo = 200,
                reloadTime = 3f,
                spread = 0.05f,
                recoil = 0.9f,
                automatic = true,
                range = 120f
            },
        };

        weaponController.grenadeCount = 3;
        weaponController.grenadeDamage = 80f;
        weaponController.grenadeRadius = 6f;
        weaponController.grenadeFuse = 2.2f;
        weaponController.grenadeThrowForce = 14f;
        weaponController.weaponView = weaponView;

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("Weapon system and first-person weapon view installed on Main Camera. Press 1/2/3/4 to switch weapons.");
    }
}
