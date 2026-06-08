using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class EffectCorrectionBuilder
{
    [MenuItem("LittleSoldier/Polish Gameplay")]
    public static void Apply()
    {
        EditorSceneManager.OpenScene("Assets/TrainingBase.unity");
        CleanupMissingScripts();
        TunePlayer();
        TuneWeapons();
        TuneWaves();
        BuildPickups();
        PolishSceneVisuals();

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        EditorSceneManager.SaveOpenScenes();
        Debug.Log("Gameplay polish applied: balance, pickups, feedback, cleanup, and scene visuals updated.");
    }

    private static void CleanupMissingScripts()
    {
        GameObject[] allObjects = Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (GameObject obj in allObjects)
            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(obj);
    }

    private static void TunePlayer()
    {
        PlayerHealth player = Object.FindFirstObjectByType<PlayerHealth>();
        if (player == null)
            return;

        player.maxHealth = 150f;
        player.currentHealth = 150f;
        player.spawnProtectionTime = 6f;
        player.damageCooldown = 0.65f;
        player.regenDelay = 5f;
        player.regenPerSecond = 10f;
        player.lowHealthRegenLimit = 75f;
    }

    private static void TuneWeapons()
    {
        WeaponController controller = Object.FindFirstObjectByType<WeaponController>();
        if (controller == null)
            return;

        controller.weapons = new Weapon[]
        {
            new Weapon
            {
                name = "\u624b\u67aa",
                damage = 32f,
                fireRate = 3.2f,
                magazineSize = 12,
                reserveAmmo = 90,
                reloadTime = 1f,
                spread = 0.003f,
                recoil = 1f,
                automatic = false,
                range = 100f
            },
            new Weapon
            {
                name = "\u6b65\u67aa",
                damage = 22f,
                fireRate = 7.5f,
                magazineSize = 30,
                reserveAmmo = 180,
                reloadTime = 1.45f,
                spread = 0.014f,
                recoil = 1.25f,
                automatic = true,
                range = 120f
            },
            new Weapon
            {
                name = "\u52a0\u7279\u6797",
                damage = 12f,
                fireRate = 15f,
                magazineSize = 90,
                reserveAmmo = 260,
                reloadTime = 2.6f,
                spread = 0.04f,
                recoil = 0.75f,
                automatic = true,
                range = 120f
            },
        };

        controller.grenadeCount = 2;
        controller.grenadeDamage = 90f;
        controller.grenadeRadius = 6.5f;
        controller.grenadeFuse = 2f;
        controller.grenadeThrowForce = 14f;
    }

    private static void TuneWaves()
    {
        WaveManager wave = Object.FindFirstObjectByType<WaveManager>();
        if (wave == null)
            return;

        wave.waves = new Wave[]
        {
            new Wave { enemyCount = 2, enemyHealth = 30f, enemyMoveSpeed = 2.05f, enemyAttackDamage = 2.5f },
            new Wave { enemyCount = 3, enemyHealth = 40f, enemyMoveSpeed = 2.35f, enemyAttackDamage = 3.2f },
            new Wave { enemyCount = 4, enemyHealth = 54f, enemyMoveSpeed = 2.7f, enemyAttackDamage = 4.2f }
        };

        wave.startDelay = 5f;
        wave.interWaveDelay = 5f;
        wave.spawnInterval = 2f;
        wave.difficulty = EnemyAI.Difficulty.Normal;
    }

    private static void BuildPickups()
    {
        DestroyIfExists("TrainingPickups");
        GameObject root = new GameObject("TrainingPickups");

        CreatePickup(root.transform, "HealthPickup_A", TrainingPickup.PickupType.Health, new Vector3(-8f, 1f, -7f));
        CreatePickup(root.transform, "HealthPickup_B", TrainingPickup.PickupType.Health, new Vector3(9f, 1f, 7f));
        CreatePickup(root.transform, "AmmoPickup_A", TrainingPickup.PickupType.Ammo, new Vector3(0f, 1f, -10f));
        CreatePickup(root.transform, "AmmoPickup_B", TrainingPickup.PickupType.Ammo, new Vector3(-13f, 1f, 5f));
        CreatePickup(root.transform, "GrenadePickup_A", TrainingPickup.PickupType.Grenade, new Vector3(13f, 1f, -9f));
    }

    private static void CreatePickup(Transform parent, string name, TrainingPickup.PickupType type, Vector3 position)
    {
        PrimitiveType primitive = type == TrainingPickup.PickupType.Health ? PrimitiveType.Cube : PrimitiveType.Sphere;
        GameObject pickup = GameObject.CreatePrimitive(primitive);
        pickup.name = name;
        pickup.transform.SetParent(parent);
        pickup.transform.position = position;
        pickup.transform.localScale = type == TrainingPickup.PickupType.Health
            ? new Vector3(0.75f, 0.35f, 0.75f)
            : Vector3.one * 0.55f;

        Collider collider = pickup.GetComponent<Collider>();
        if (collider != null)
            collider.isTrigger = true;

        TrainingPickup script = pickup.AddComponent<TrainingPickup>();
        script.type = type;
        script.healAmount = 60f;
        script.pistolAmmo = 18;
        script.rifleAmmo = 60;
        script.gatlingAmmo = 80;
        script.grenades = 1;

        Renderer renderer = pickup.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = MakeMaterial(script.GetColor());
    }

    private static void PolishSceneVisuals()
    {
        RenderSettings.ambientLight = new Color(0.48f, 0.52f, 0.56f);
        Camera camera = Camera.main;
        if (camera != null)
        {
            camera.backgroundColor = new Color(0.48f, 0.62f, 0.78f);
            camera.nearClipPlane = 0.03f;
        }

        SetMaterial("Ground", new Color(0.36f, 0.42f, 0.43f));
        SetMaterial("Wall_N", new Color(0.54f, 0.58f, 0.64f));
        SetMaterial("Wall_S", new Color(0.54f, 0.58f, 0.64f));
        SetMaterial("Wall_E", new Color(0.42f, 0.46f, 0.52f));
        SetMaterial("Wall_W", new Color(0.42f, 0.46f, 0.52f));

        GameObject extras = GameObject.Find("MapExtras");
        if (extras != null)
        {
            foreach (Transform child in extras.transform)
            {
                Color color = child.name.ToLower().Contains("cover")
                    ? new Color(0.36f, 0.48f, 0.34f)
                    : new Color(0.48f, 0.5f, 0.52f);
                Renderer renderer = child.GetComponent<Renderer>();
                if (renderer != null)
                    renderer.sharedMaterial = MakeMaterial(color);
            }
        }
    }

    private static void SetMaterial(string name, Color color)
    {
        GameObject obj = GameObject.Find(name);
        if (obj == null)
            return;

        Renderer renderer = obj.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = MakeMaterial(color);
    }

    private static Material MakeMaterial(Color color)
    {
        Shader shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null)
            shader = Shader.Find("Standard");

        Material material = new Material(shader);
        material.color = color;
        return material;
    }

    private static void DestroyIfExists(string name)
    {
        GameObject obj = GameObject.Find(name);
        if (obj != null)
            Object.DestroyImmediate(obj);
    }
}
