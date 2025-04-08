import os
from time import sleep
from multiprocessing import Manager, Process
from typing import NamedTuple

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

import TFTBot as tb
from TFTBot import initialize_shared_state
import envs

class Info(NamedTuple):
    """
    Represents information about a Discord server and channel.

    Attributes:
        server_id (str): The unique identifier of the server.
        channel_id (str): The unique identifier of the channel.
        server (str): The name of the server.
        channel (str): The name of the channel.
    """
    server_id: str
    channel_id: str
    server: str
    channel: str


class ChatMessage(NamedTuple):
    """
    Represents a chat message in the Discord channel.

    Attributes:
        username (str): The name of the user who sent the message.
        is_bot (bool): Indicates whether the message was sent by a bot.
        timestamp (str): The timestamp of the message in ISO 8601 format.
        reactions (list[WebElement]): A list of WebElements representing the reactions to the message.
        reaction_list (list[WebElement]): A list of WebElements representing individual reactions.
        embed_title (str): The title of any embedded content in the message.
        embed_description (str): The description of any embedded content in the message.
    """
    username: str
    is_bot: bool
    timestamp: str
    content: str
    reactions: list[WebElement]
    embed_title: str
    embed_description: str 


def start_bot(shared_dict):
    """
    Initializes the shared state and starts the TFT Bot.

    This function sets up the shared state using the provided dictionary
    and then runs the TFT Bot using the Riot API key and Discord token
    retrieved from environment variables.

    Args:
        shared_dict (dict): A dictionary used to initialize the shared state.

    Environment Variables:
        RIOT_API_KEY (str): The API key for accessing Riot's API.
        DISCORD_TOKEN (str): The token for authenticating with Discord.

    Raises:
        KeyError: If the required environment variables are not set.
    """
    initialize_shared_state(shared_dict)
    tb.run(os.environ["RIOT_API_KEY"], os.environ["DISCORD_TOKEN"])  


@pytest.fixture(scope="session")
def info():
    """
    Returns an Info object containing details about a specific server and channel.

    Returns:
        Info: An object with the following attributes:
            - server_id (str): The unique identifier of the server.
            - channel_id (str): The unique identifier of the channel.
            - server (str): The name of the server.
            - channel (str): The name of the channel.
    """
    return Info(
        server_id="1344408466298634310",
        channel_id="1344408466801823766",
        server="Matija's server",
        channel="#general"
    )


@pytest.fixture(autouse=True, scope="session")
def setup():
    """
    Sets up the environment and initializes a bot process for testing.
    This function performs the following steps:
    1. Sets up the required environment variables using `envs.set_envs()`.
    2. Creates a shared dictionary using `multiprocessing.Manager` to facilitate inter-process communication.
    3. Starts the bot in a separate process, passing the shared dictionary as an argument.
    4. Yields the shared dictionary for use in tests.
    5. Ensures the bot process is terminated and cleaned up after the tests are completed.
    Yields:
        shared_dict (multiprocessing.managers.DictProxy): A shared dictionary for inter-process communication.
    """
    envs.set_envs()

    # Create a shared dictionary using multiprocessing.Manager
    manager = Manager()
    shared_dict = manager.dict()

    # Start the bot in a separate process
    bot_process = Process(target=start_bot, args=(shared_dict,))
    bot_process.start()

    # Wait for the bot to initialize (optional, if needed)
    yield shared_dict

    # Terminate the bot process after tests
    bot_process.terminate()
    bot_process.join()


@pytest.fixture(scope="session")
def driver(info: Info):
    """
    Automates the process of logging into Discord and navigating to a specific server and channel.
    Args:
        info (Info): An object containing the necessary information for the Discord server and channel.
            - info.server_id (str): The ID of the Discord server to navigate to.
            - info.channel_id (str): The ID of the Discord channel to navigate to.
            - info.server (str): The name of the Discord server (used for validation).
            - info.channel (str): The name of the Discord channel (used for validation).
    Returns:
        WebDriver: An instance of the Selenium WebDriver after successfully logging in and navigating.
    Raises:
        AssertionError: If the login fails or the server/channel validation fails.
    """
    driver = webdriver.Chrome()
    driver.implicitly_wait(10.0)
    # Navigate to the Discord login page and server redirect
    driver.get(f"https://discord.com/login?redirect_to=/channels/{info.server_id}/{info.channel_id}") # Matijas server
    
    # Log in to Discord
    email = driver.find_element(By.XPATH, "//input[@name='email']")
    email.send_keys(os.environ["DISCORD_USER"])
    password = driver.find_element(By.XPATH, "//input[@name='password']")
    password.send_keys(os.environ["DISCORD_PW"])
    login = driver.find_element(By.XPATH, "//button[@type='submit']")
    login.click()

    # Wait for the login to complete and the server/channel to load
    # set timout really high to have time to solve captcha
    WebDriverWait(driver, 60).until(
        lambda d: d.find_element(By.XPATH, "//div[starts-with(@class, 'messagesWrapper')]")
    )

    if info.server in driver.title and info.channel in driver.title:
        return driver
    else:
        pytest.fail("Login failed or incorrect server/channel in login fixture.")


def get_reaction_count(reactions: list[WebElement]) -> int | None:
    """
    Extracts and returns the count of reactions from a given WebElement.

    Args:
        reaction (WebElement): The web element representing a reaction.

    Returns:
        int | None: The count of reactions as an integer if the count is a digit,
                    otherwise None.
    """
    rc = []
    for reaction in reactions:
        t = reaction.find_element(By.XPATH, ".//div[starts-with(@class, 'reactionCount')]").text
        if t.isdigit():
            rc.append(int(t))
    return rc


def get_latest_chatmessage(driver: webdriver.Chrome) -> ChatMessage:
    """
    Retrieves the latest chat message from a web application's chat interface.
    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance used to interact with the web application.
    Returns:
        ChatMessage: An object containing details of the latest chat message, including:
            - username (str): The username of the message sender.
            - is_bot (bool): Whether the message sender is a bot.
            - timestamp (str): The timestamp of the message in ISO 8601 format.
            - reactions (list[WebElement]): A list of WebElements representing the reactions to the message.
            - reaction_list (list[WebElement]): A list of WebElements representing individual reactions.
            - embed_title (str): The title of any embedded content in the message.
            - embed_description (str): The description of any embedded content in the message.
    Raises:
        TimeoutException: If the chat content or message elements are not found within the specified timeout.
        NoSuchElementException: If specific elements within the message are not found.
    """
    chatContent: WebElement = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.XPATH, "//div[starts-with(@class, 'messagesWrapper')]")
    )

    message = chatContent.find_elements(By.XPATH, "//li[starts-with(@id, 'chat-messages')]")[-1]

    
    username = message.find_element(By.XPATH, ".//span[starts-with(@class, 'username')]").text
    bot_cosy = message.find_elements(By.XPATH, ".//span[starts-with(@class, 'botTagCozy')]")
    is_bot = True if len(bot_cosy) > 0 and bot_cosy[0].text == "APP" else False
    timestamp = message.find_element(By.XPATH, ".//time").get_attribute("datetime")

    content = message.find_element(By.XPATH, ".//div[starts-with(@id, 'message-content')]").get_attribute("innerHTML")
    message_accessories = message.find_element(By.XPATH, ".//div[starts-with(@id, 'message-accessories')]")
    reactions = message_accessories.find_elements(By.XPATH, ".//div[starts-with(@class, 'reactionInner')]")
    ett = message.find_elements(By.XPATH, ".//div[starts-with(@class, 'embedTitle')]")
    embed_title = ett[0].find_element(By.XPATH, ".//span").text if len(ett) > 0 else None
    edt = message.find_elements(By.XPATH, ".//div[starts-with(@class, 'embedDescription')]")
    embed_description = edt[0].get_attribute("innerHTML") if len(edt) > 0 else None

    return ChatMessage(
        username=username,
        is_bot=is_bot,
        timestamp=timestamp,
        content=content,
        reactions=reactions,
        embed_title=embed_title,
        embed_description=embed_description
    )


def get_chatmessage(driver: webdriver.Chrome, info: Info, msg_id: int) -> ChatMessage:
    """
    Retrieves a chat message from a web page using Selenium.
    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance used to interact with the web page.
        info (Info): An object containing information about the chat, including the channel ID.
        msg_id (int): The unique identifier of the chat message to retrieve.
    Returns:
        ChatMessage: An object containing details of the chat message, including:
            - username (str): The username of the message sender.
            - is_bot (bool): Whether the sender is a bot.
            - timestamp (str): The timestamp of the message in ISO 8601 format.
            - reactions (list[WebElement]): A list of WebElement objects representing the reactions to the message.
            - reaction_list (list[WebElement]): A list of WebElement objects representing individual reactions.
            - embed_title (str): The title of the embedded content in the message.
            - embed_description (str): The description of the embedded content in the message.
    Raises:
        TimeoutException: If the chat content or message elements are not found within the specified timeout.
        NoSuchElementException: If any of the required elements are not found on the web page.
    """
    message: WebElement = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.XPATH, f"//li[starts-with(@id, 'chat-messages-{info.channel_id}-{msg_id}')]")
    )
    
    username = message.find_element(By.XPATH, ".//span[starts-with(@class, 'username')]").text
    bot_cosy = message.find_elements(By.XPATH, ".//span[starts-with(@class, 'botTagCozy')]")
    is_bot = True if len(bot_cosy) > 0 and bot_cosy[0].text == "APP" else False
    timestamp = message.find_element(By.XPATH, ".//time").get_attribute("datetime")

    content = message.find_element(By.XPATH, ".//div[starts-with(@id, 'message-content')]").get_attribute("innerHTML")
    message_accessories = message.find_element(By.XPATH, f".//div[starts-with(@id, 'message-accessories-{msg_id}')]")
    reactions = message_accessories.find_elements(By.XPATH, ".//div[starts-with(@class, 'reactionInner')]")
    ett = message.find_elements(By.XPATH, ".//div[starts-with(@class, 'embedTitle')]")
    embed_title = ett[0].find_element(By.XPATH, ".//span").text if len(ett) > 0 else None
    edt = message.find_elements(By.XPATH, ".//div[starts-with(@class, 'embedDescription')]")
    embed_description = edt[0].get_attribute("innerHTML") if len(edt) > 0 else None

    return ChatMessage(
        username=username,
        is_bot=is_bot,
        timestamp=timestamp,
        content=content,
        reactions=reactions,
        embed_title=embed_title,
        embed_description=embed_description
    )


def chat_box(driver: webdriver.Chrome) -> WebElement:
    """
    Locate and return the chat box element within a web page.

    This function navigates through the DOM structure to find the chat box
    element by first locating the bottom bar area, then the text area, and
    finally the textbox element.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance used to
            interact with the web page.

    Returns:
        WebElement: The WebElement representing the chat box (textbox) element.

    Raises:
        NoSuchElementException: If any of the required elements (bottom bar,
            text area, or textbox) cannot be found on the page.
    """
    bottom_bar: WebElement = driver.find_element(By.XPATH, "//div[starts-with(@class, 'channelBottomBarArea')]")
    text_area = bottom_bar.find_element(By.XPATH, "//div[starts-with(@class, 'textArea')]")
    return text_area.find_element(By.XPATH, "//div[@role='textbox']")


# Test cases for the chat bot functionality

def get_latest_msg_id(setup: dict) -> int:
    """
    Retrieves the latest message ID from the shared dictionary.

    Args:
        setup (dict): A dictionary containing the latest message ID.

    Returns:
        int: The latest message ID.
    """
    b = len(setup)
    while b == len(setup):
        sleep(0.1)
    
    latest_message_id, _ = next(reversed(setup.items()))
    return latest_message_id


def test_analyze_success(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the functionality of the "!analyze" command in the chat bot.
    This test sends the "!analyze" command with a summoner name to the chat bot,
    waits for the bot's response, and verifies that the response contains the
    expected information.
    """
    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    latest_message_id = get_latest_msg_id(setup)

    m = get_chatmessage(driver, info, latest_message_id)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert summoner in m.embed_title


def test_analyze_could_not_find_summoner(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the bot when the `!analyze` command is issued with a summoner name that cannot be found.
    """
    cb = chat_box(driver)
    summoner = "Loading"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    sleep(3) # Wait for the bot to respond

    m = get_latest_chatmessage(driver)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert "Error" in m.embed_title
    assert summoner in m.embed_description
    assert "Could not find summoner" in m.embed_description


def test_analyze_no_match_history(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the bot when the `!analyze` command is issued for a summoner with no match history.
    """
    cb = chat_box(driver)
    summoner = "Lisko34/NA1"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    sleep(3)  # Wait for the bot to respond

    m = get_latest_chatmessage(driver)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert "Error" in m.embed_title
    assert "Could not fetch match history" in m.embed_description


def test_analyze_multiple_pages(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the bot when the `!analyze` command generates multiple pages of results.
    """
    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    latest_message_id = get_latest_msg_id(setup)

    m = get_chatmessage(driver, info, latest_message_id)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert summoner in m.embed_title

    # Simulate navigating to the next page
    m.reactions[1].click()  # Click on the reactions to open the reaction menu

    sleep(3)  # Wait for the page to update

    m = get_chatmessage(driver, info, latest_message_id)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert "Page 2" in m.embed_title


def test_reaction_navigation(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the bot's reaction-based navigation functionality.
    """
    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    latest_message_id = get_latest_msg_id(setup)

    m = get_chatmessage(driver, info, latest_message_id)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert summoner in m.embed_title

    # Simulate clicking the next page reaction
    m.reactions[1].click()  # Click on the reactions to open the reaction menu

    sleep(3)  # Wait for the page to update

    m = get_chatmessage(driver, info, latest_message_id)
    assert "Page 2" in m.embed_title

    # Simulate clicking the previous page reaction
    m.reactions[0].click()  # Click on the reactions to open the reaction menu

    sleep(3)  # Wait for the page to update

    m = get_chatmessage(driver, info, latest_message_id)
    assert "Page 1" in m.embed_title


def test_analyze_missing_summoner_name(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the bot when the `!analyze` command is issued without a summoner name.
    """
    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    first_id = get_latest_msg_id(setup)
    
    cb = chat_box(driver)
    cb.send_keys("!analyze ")
    cb.send_keys(Keys.RETURN)

    sleep(3)  # Wait for the bot to respond

    n = get_latest_chatmessage(driver)
    assert "!analyze" in n.content # discord trimms whitespace, so we need to check if the command is in the content

def test_analyze_special_characters(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the bot when the `!analyze` command is issued with a summoner name containing special characters.
    """
    cb = chat_box(driver)
    special_characters = "!@#$%^&*()"
    cb.send_keys(f"!analyze {special_characters}")
    cb.send_keys(Keys.RETURN)

    sleep(3)  # Wait for the bot to respond

    m = get_latest_chatmessage(driver)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert "Error" in m.embed_title
    assert "Could not find summoner" in m.embed_description


def test_analyze_with_old_message_id(driver: webdriver.Chrome, info: Info, setup: dict):
    """
    Tests the behavior of the "!analyze" command in a chat bot when invoked multiple times 
    with the same summoner name and verifies the handling of old message IDs.
    """
    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    first_msg = get_latest_msg_id(setup)

    m = get_chatmessage(driver, info, first_msg)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert summoner in m.embed_title

    cb = chat_box(driver)
    summoner = "Loading/2830"
    cb.send_keys(f"!analyze {summoner}")
    cb.send_keys(Keys.RETURN)

    second_msg = get_latest_msg_id(setup)

    m = get_chatmessage(driver, info, second_msg)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert summoner in m.embed_title

    m = get_chatmessage(driver, info, first_msg)
    m.reactions[1].click()  # Click on the reactions to open the reaction menu

    sleep(3)  # Wait for the page to update

    m = get_chatmessage(driver, info, first_msg)
    assert m.username == "Matija"
    assert m.is_bot is True
    assert "Page 2" in m.embed_title
